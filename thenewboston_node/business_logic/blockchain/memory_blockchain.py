import copy
import logging
from itertools import islice
from typing import Generator, Optional

from thenewboston_node.business_logic.exceptions import MissingEarlierBlocksError, ValidationError
from thenewboston_node.business_logic.models.account_root_file import AccountRootFile
from thenewboston_node.business_logic.models.block import Block

from .base import BlockchainBase

logger = logging.getLogger(__name__)


class MemoryBlockchain(BlockchainBase):
    """
    A blockchain implementation primarily for use in unittesting and being used as an example implementation
    """

    def __init__(self, *, initial_account_root_file):
        self.account_root_files: list[AccountRootFile] = [AccountRootFile.from_dict(initial_account_root_file)]

        self.blocks: list[Block] = []

    def persist_block(self, block: Block):
        self.blocks.append(copy.deepcopy(block))

    def get_head_block(self) -> Optional[Block]:
        blocks = self.blocks
        if blocks:
            return blocks[-1]

        return None

    def get_block_by_number(self, block_number: int) -> Optional[Block]:
        if block_number < 0:
            raise ValueError('block_number must be greater or equal to 0')

        blocks = self.blocks
        if not blocks:
            return None

        head_block_number = blocks[-1].message.block_number
        if block_number > head_block_number:
            return None

        block_index = block_number - head_block_number - 1
        try:
            return blocks[block_index]
        except IndexError:
            assert blocks[0].message.block_number > block_number
            raise MissingEarlierBlocksError()

    def get_blocks_until_account_root_file(self, start_block_number: Optional[int] = None):
        """
        Return generator of block traversing from `start_block_number` block (or head block if not specified)
        to the block in included in the closest account root file (exclusive: the account root file block is not
        traversed).
        """
        if start_block_number is not None and start_block_number < 0:
            return

        blocks = self.blocks
        if not blocks:
            return

        account_root_file = self.get_closest_account_root_file(start_block_number)
        if account_root_file is None:
            return

        account_root_file_block_number = account_root_file.last_block_number
        assert (
            start_block_number is None or account_root_file_block_number is None or
            account_root_file_block_number <= start_block_number
        )

        current_head_block = blocks[-1]
        current_head_block_number = current_head_block.message.block_number
        offset = 0 if start_block_number is None else (current_head_block_number - start_block_number)

        if account_root_file_block_number is None:
            blocks_to_return = len(blocks) - offset
        else:
            blocks_to_return = current_head_block_number - account_root_file_block_number - offset

        # TODO(dmu) HIGH: Consider performance optimizations for islice(reversed(blocks), offset, blocks_to_return, 1)
        for block in islice(reversed(blocks), offset, offset + blocks_to_return, 1):
            assert (
                account_root_file_block_number is None or account_root_file_block_number < block.message.block_number
            )

            yield block

    def _get_balance_from_block(self, account: str, block_number: Optional[int] = None) -> Optional[int]:
        for block in self.get_blocks_until_account_root_file(block_number):
            balance = block.message.get_balance(account)
            if balance is not None:
                return balance.balance

        return None

    def _get_balance_from_account_root_file(self, account: str, block_number: Optional[int] = None) -> Optional[int]:
        account_root_file = self.get_closest_account_root_file(block_number)
        assert account_root_file
        return account_root_file.get_balance_value(account)

    def get_account_balance(self, account: str, block_number: Optional[int] = None) -> Optional[int]:
        """
        Returns account balance for the specified account. If block_number is specified then
        the account balance for that block is returned (after the block_number block is applied)
        otherwise the current (head block) balance is returned. If block_number is equal to -1 then
        account balance before 0 block is returned.
        """
        if block_number is not None and block_number < -1:
            raise ValueError('block_number must be greater or equal to -1')

        balance = self._get_balance_from_block(account, block_number)
        if balance is None:
            balance = self._get_balance_from_account_root_file(account, block_number)

        return balance

    def get_account_balance_lock(self, account: str) -> str:
        for block in self.get_blocks_until_account_root_file():
            balance = block.message.get_balance(account)
            if balance is not None:
                balance_lock = balance.balance_lock
                if balance_lock:
                    return balance_lock

        account_root_file = self.get_closest_account_root_file()
        assert account_root_file
        return account_root_file.get_balance_lock(account)

    def get_last_account_root_file(self) -> Optional[AccountRootFile]:
        account_root_files = self.account_root_files
        if account_root_files:
            return account_root_files[-1]

        return None

    def get_first_account_root_file(self) -> Optional[AccountRootFile]:
        account_root_files = self.account_root_files
        if account_root_files:
            return account_root_files[0]

        return None

    def get_account_root_files_reversed(self) -> Generator[AccountRootFile, None, None]:
        yield from reversed(self.account_root_files)

    def validate(self, block_offset: int = None, block_limit: int = None):
        self.validate_account_root_files()
        self.validate_blocks()

    def validate_account_root_files(self):
        account_root_files = self.account_root_files
        if not account_root_files:
            raise ValidationError('Blockchain must contain at least one account root file')

        # TODO(dmu) HIGH: Reimplement allowing partial blockchains
        # if not account_root_files[0].is_initial():
        #     raise ValidationError('First account root file must be initial account root file')
        #
        # account_root_files[0].validate(is_initial=True)
        # for account_root_file in islice(account_root_files, 1):
        #     # TODO(dmu) CRITICAL: Validate last_block_number and last_block_identifiers point to correct blocks
        #     account_root_file.validate()

    def validate_blocks(self, offset: Optional[int] = None, limit: Optional[int] = None):
        # Validations to be implemented:
        # 1. Block numbers are sequential
        # 2. Block identifiers equal to previous block message hash
        # 3. Each individual block is valid
        # 4. First block identifier equals to initial account root file hash

        blocks = self.blocks
        if offset is not None or limit is not None:
            start = offset or 0
            if limit is None:
                blocks_iter = islice(blocks, start)
            else:
                blocks_iter = islice(blocks, start, start + limit)
        else:
            blocks_iter = iter(blocks)

        for block in blocks_iter:
            block.validate(self)

        raise NotImplementedError