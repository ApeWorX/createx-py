import pytest
from ape.contracts import ContractContainer
from createx import CreateX


@pytest.fixture(scope="session")
def deployer(accounts):
    return accounts[0]


@pytest.fixture(scope="session")
def TestContract(compilers):
    solidity = compilers.registered_compilers[".sol"]
    contract_type = solidity.compile_code("contract TestContract {}")
    contract_type.name = "TestContract"
    return ContractContainer(contract_type=contract_type)


@pytest.fixture(scope="session")
def createx(chain):
    return CreateX.inject()
