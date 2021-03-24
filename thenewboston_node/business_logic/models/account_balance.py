import logging
from dataclasses import dataclass
from typing import Optional

from dataclasses_json import dataclass_json

from thenewboston_node.business_logic.exceptions import ValidationError
from thenewboston_node.core.utils.constants import SENTINEL
from thenewboston_node.core.utils.dataclass import fake_super_methods

logger = logging.getLogger(__name__)
validation_logger = logging.getLogger(__name__ + '.validation_logger')


@dataclass_json
@dataclass
class AccountBalance:
    value: int
    lock: str

    def validate(self, validate_lock=True):
        validation_logger.debug('Validating account balance attributes')
        if not isinstance(self.value, int):
            raise ValidationError('Account balance value must be an integer')
        validation_logger.debug('Account balance value is an integer')

        if validate_lock:
            if not isinstance(self.lock, str):
                raise ValidationError('Account balance lock must be a string')
            validation_logger.debug('Account balance lock is a string')

            if not self.lock:
                raise ValidationError('Account balance lock must be set')
            validation_logger.debug('Account balance lock is set')

        validation_logger.debug('Account balance attributes are valid')


@fake_super_methods
@dataclass_json
@dataclass
class BlockAccountBalance(AccountBalance):
    lock: Optional[str] = None  # type: ignore

    def override_to_dict(self):  # this one turns into to_dict()
        dict_ = self.super_to_dict()

        # TODO(dmu) LOW: Implement a better way of removing optional fields or allow them in normalized message
        value = dict_.get('lock', SENTINEL)
        if value is None:
            del dict_['lock']

        return dict_

    def validate(self):
        super().validate(validate_lock=False)
