import pytest
from createx.main import CreationType
from eth_utils.crypto import keccak


@pytest.mark.parametrize(
    "create_type,salt",
    [
        (CreationType.CREATE, None),
        (CreationType.CREATE2, None),
        (CreationType.CREATE2, b"salt"),
    ],
)
def test_deployment_without_args(deployer, TestContract, createx, create_type, salt):
    contract = createx.deploy(
        TestContract,
        create_type=create_type,
        salt=salt,
        sender=deployer,
    )

    receipt = deployer.history[-1]
    assert contract.address == receipt.return_value
    assert receipt.events == [
        createx.contract.ContractCreation(newContract=contract.address),
    ]

    if create_type is CreationType.CREATE:
        precomputed_address = createx.compute_address(
            TestContract,
            create_type=create_type,
            nonce=createx.contract.nonce - 1,
        )

    elif salt is not None:
        assert (
            createx.compute_guarded_salt(salt, sender_address=deployer.address)
            == receipt.events[0].salt
        )
        precomputed_address = createx.compute_address(
            TestContract,
            create_type=create_type,
            salt=salt,
            sender_address=deployer.address,
        )

    else:  # cannot pre-compute
        # NOTE: We have to compute this manually using the value from `_generateSalt`
        #       (sourced from event log)as it is highly dependent on chain-conditions
        precomputed_address = createx.contract.computeCreate2Address(
            receipt.events[0].salt,
            keccak(TestContract.contract_type.deployment_bytecode.to_bytes()),
        )

    assert precomputed_address == contract.address
