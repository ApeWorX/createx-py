from enum import Enum
from functools import cached_property
from typing import TYPE_CHECKING

from ape.types import AddressType, HexBytes
from ape.utils import ZERO_ADDRESS, ManagerAccessMixin
from eth_abi import abi
from eth_utils.address import to_canonical_address
from eth_utils.crypto import keccak

from . import package

if TYPE_CHECKING:
    from ape.contracts import ContractContainer, ContractInstance


class CreationType(str, Enum):
    CREATE = "create"
    """
    Read-only:
    - computeCreateAddress(uint256) view returns (address)
    - computeCreateAddress(address,uint256) view returns (address)

    Write:
    - deployCreate(bytes)
    - deployCreateAndInit(bytes,bytes,tuple(uint256,uint256)) payable returns (address)
    - deployCreateAndInit(bytes,bytes,tuple(uint256,uint256),address) payable returns (address)
    """

    CREATE2 = "create2"
    """
    Read-only:
    - computeCreate2Address(bytes32,bytes32) view returns (address)
    - computeCreate2Address(bytes32,bytes32,address) pure returns (address)

    Write:
    - deployCreate2(bytes) payable returns (address)
    - deployCreate2(bytes32,bytes) payable returns (address)
    - deployCreate2AndInit(bytes,bytes,tuple(uint256,uint256)) payable returns (address)
    - deployCreate2AndInit(bytes32,bytes,bytes,tuple(uint256,uint256)) payable returns (address)
    - deployCreate2AndInit(bytes,bytes,tuple(uint256,uint256),address) payable returns (address)
    - deployCreate2AndInit(bytes32,bytes,bytes,tuple(uint256,uint256),address) payable returns (address)
    """

    # TODO: CREATE3 = "create3"


class CreateX(ManagerAccessMixin):
    def __init__(self):
        if (
            self.provider.chain_id not in package.DEPLOYED_CHAIN_IDS
            and not self.provider.get_code(package.DEPLOYED_ADDRESS)
        ):
            raise RuntimeError(
                "Not available on this chain. Please use `CreateX.inject` or deploy manually."
            )

    @classmethod
    def inject(cls):
        # NOTE: Injection must be done using this account w/ `nonce=0`
        deployer = cls.account_manager.test_accounts.impersonate_account(
            package.DEPLOYER
        )
        assert deployer.nonce == 0

        manifest = package.get_manifest()
        cx = deployer.deploy(manifest.CreateX, gas_price=0)
        assert cx.address == package.DEPLOYED_ADDRESS

        return cls()

    @property
    def address(self) -> AddressType:
        return package.DEPLOYED_ADDRESS

    @cached_property
    def contract(self) -> "ContractInstance":
        manifest = package.get_manifest()
        return self.chain_manager.contracts.instance_at(
            self.address,
            contract_type=manifest.CreateX,
            fetch_from_explorer=False,
            detect_proxy=False,
        )

    def encode_salt(
        self,
        salt: HexBytes | str,
        sender_address: AddressType = ZERO_ADDRESS,
        redeploy_protection: bool = True,
    ) -> HexBytes:
        if isinstance(salt, str):
            salt = salt.encode(encoding="utf-8")

        assert isinstance(salt, bytes)  # mypy happy
        if len(salt) > 11:
            salt = keccak(salt)[:11]

        elif len(salt) < 11:
            salt = b"\x00" * (11 - len(salt)) + salt

        assert isinstance(sender_address, str)  # mypy happy
        return HexBytes(
            to_canonical_address(sender_address)
            + (b"\x01" if redeploy_protection else b"\x00")
            + salt
        )

    def compute_guarded_salt(
        self,
        salt: HexBytes | str,
        sender_address: AddressType = ZERO_ADDRESS,
        sender_protection: bool = True,
        redeploy_protection: bool = True,
    ) -> HexBytes:
        if sender_protection and sender_address == ZERO_ADDRESS:
            raise RuntimeError(
                "Must provide `sender_address` if `sender_protection=True`."
            )

        encoded_salt = self.encode_salt(
            salt,
            sender_address=sender_address,
            redeploy_protection=redeploy_protection,
        )

        if sender_protection and redeploy_protection:
            encoded_salt = abi.encode(
                ("address", "uint256", "bytes32"),
                (sender_address, self.provider.chain_id, encoded_salt),
            )

        elif sender_protection and not redeploy_protection:
            encoded_salt = abi.encode(
                ("address", "bytes32"),
                (sender_address, encoded_salt),
            )

        elif not sender_protection and redeploy_protection:
            encoded_salt = abi.encode(
                ("uint256", "bytes32"),
                (self.provider.chain_id, encoded_salt),
            )

        # else: use the original salt value (doesn't handle `_generateSalt()` case)

        assert isinstance(encoded_salt, bytes)  # mypy happy
        return HexBytes(keccak(encoded_salt))

    def compute_address(
        self,
        Contract: "ContractContainer",
        *constructor_args,
        create_type: CreationType | str = CreationType.CREATE2,
        nonce: int | None = None,
        salt: HexBytes | str | None = None,
        sender_address: AddressType = ZERO_ADDRESS,
        sender_protection: bool = True,
        redeploy_protection: bool = True,
    ) -> AddressType:
        if not isinstance(create_type, CreationType):
            create_type = CreationType(create_type)

        match create_type:
            case CreationType.CREATE:
                if salt is not None:
                    raise RuntimeError("`salt=` is not supported for CREATE.")

                compute_address_fn = self.contract.computeCreateAddress
                args = [self.contract.nonce if nonce is None else nonce]

            case CreationType.CREATE2:
                if nonce is not None:
                    raise RuntimeError("`nonce=` is not supported for CREATE2.")

                elif salt is None:
                    # NOTE: Raise here since it's impossible to accurately compute
                    #       `_generateSalt()` ahead of time
                    raise RuntimeError(
                        "Cannot compute CREATE2 address if no salt provided."
                    )

                compute_address_fn = self.contract.computeCreate2Address
                args = [
                    self.compute_guarded_salt(
                        salt,
                        sender_address=sender_address,
                        sender_protection=sender_protection,
                        redeploy_protection=redeploy_protection,
                    ),
                    keccak(  # initcode hash
                        Contract.constructor.serialize_transaction(
                            *constructor_args
                        ).data
                    ),
                ]

        return compute_address_fn(*args)

    def deploy(
        self,
        Contract: "ContractContainer",
        *constructor_args,
        create_type: CreationType | str = CreationType.CREATE2,
        salt: HexBytes | str | None = None,
        refund: AddressType | str | None = None,
        deployment_payable_value: int = 0,
        initialization_payable_value: int = 0,
        sender_protection: bool = True,
        redeploy_protection: bool = True,
        init_args: bytes | None = None,
        **txn_args,
    ) -> "ContractInstance":
        if not isinstance(create_type, CreationType):
            create_type = CreationType(create_type)

        match create_type:
            case CreationType.CREATE:
                if salt is not None:
                    raise RuntimeError("`salt=` is not supported for CREATE")

                if (
                    init_args
                    or deployment_payable_value
                    or initialization_payable_value
                ):
                    deployment_fn = self.contract.deployCreateAndInit
                    args = [
                        # Initcode for contract
                        Contract.constructor.serialize_transaction(
                            *constructor_args
                        ).data,
                        # Post-deploy init args for contract
                        init_args or b"",
                        # Payable values to use for deployment and initialization
                        (deployment_payable_value, initialization_payable_value),
                    ]

                else:
                    deployment_fn = self.contract.deployCreate
                    args = [
                        # Initcode for contract
                        Contract.constructor.serialize_transaction(
                            *constructor_args
                        ).data,
                    ]

            case CreationType.CREATE2:
                if (
                    init_args
                    or deployment_payable_value
                    or initialization_payable_value
                ):
                    deployment_fn = self.contract.deployCreate2AndInit
                    args = [
                        # Initcode for contract
                        Contract.constructor.serialize_transaction(
                            *constructor_args
                        ).data,
                        # Post-deploy init args for contract
                        init_args or b"",
                        # Payable values to use for deployment and initialization
                        (deployment_payable_value, initialization_payable_value),
                    ]

                else:
                    deployment_fn = self.contract.deployCreate2
                    args = [
                        # Initcode for contract
                        Contract.constructor.serialize_transaction(
                            *constructor_args
                        ).data,
                    ]

        if refund is not None:
            # If applicable, last Arg becomes Refund address in all cases
            args.append(refund)

        if create_type is not CreationType.CREATE and (
            salt is not None or redeploy_protection or sender_protection
        ):
            if sender_protection:
                if not (
                    sender := txn_args.get(
                        "sender", self.account_manager.default_sender
                    )
                ):
                    raise ValueError(
                        "Must provide `sender=` to use `sender_protection=True`."
                    )

                sender_address = self.conversion_manager.convert(sender, AddressType)

            else:
                sender_address = ZERO_ADDRESS

            # If applicable, first Arg becomes salt in all supported cases
            encoded_salt = self.encode_salt(
                salt or "",
                sender_address=sender_address,
                redeploy_protection=redeploy_protection,
            )
            args.insert(0, encoded_salt)

        receipt = deployment_fn(*args, **txn_args)
        return Contract.at(
            # NOTE: This is always supported (doesn't require traces like `.return_value` does)
            receipt.events[0].newContract,  # NOTE: Should always be 1st event log
            fetch_from_explorer=False,
            detect_proxy=False,
        )
