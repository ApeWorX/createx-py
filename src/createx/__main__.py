import random
import warnings
from typing import TYPE_CHECKING

import click
from ape.cli import ConnectedProviderCommand, account_option
from ape.types.address import AddressType
from ape.utils.misc import ZERO_ADDRESS
from eth_utils.address import to_canonical_address
from eth_utils.conversions import to_bytes

from createx import CreateX
from createx.main import CreationType

if TYPE_CHECKING:
    from ape.api import AccountAPI
    from ape.contracts import ContractContainer
    from ape.types import HexBytes


@click.group()
def cli():
    """CLI for interacting with CreateX"""


def get_contract_type(ctx, param, value):
    from ape import project

    if ":" in value:
        if (
            len(dependency_path := value.split(":")) == 2
            and len(dependency_version := dependency_path[0].split("@")) == 2
        ):
            for dependency in project.dependencies.get_versions(dependency_version[0]):
                if dependency.version == dependency_version[1]:
                    if not (
                        Contract := dependency.project.contracts.get(dependency_path[1])
                    ):
                        break

                    return Contract

        raise click.BadParameter(
            ctx=ctx,
            param=param,
            message=f"'{value}' is not a valid dependency specifier.",
        )

    elif Contract := project.contracts.get(value):
        return Contract

    raise click.BadParameter(
        ctx=ctx,
        param=param,
        message=f"'{value}' is not a type in your local project.",
    )


def convert_salt(ctx, param, value):
    try:
        # If hexstr, will convert to HexBytes
        return to_bytes(hexstr=value)

    except Exception:
        return value


@cli.command(cls=ConnectedProviderCommand)
@click.option("--type", "create_type", type=CreationType, default=CreationType.CREATE2)
@click.option("--nonce", type=int, default=None)
@click.option("--salt", callback=convert_salt, default=None)
@account_option("--deployer", prompt="Account to deploy with")
@click.option("--sender-protection/--no-sender-protection", default=True)
@click.option("--redeploy-protection/--no-redeploy-protection", default=True)
@click.argument("contract_type", metavar="CONTRACT", callback=get_contract_type)
@click.argument("constructor_args", metavar="ARGS", nargs=-1)
def address(
    create_type: CreationType,
    nonce: int | None,
    salt: "HexBytes | str | None",
    deployer: "AccountAPI",
    sender_protection: bool,
    redeploy_protection: bool,
    contract_type: "ContractContainer",
    constructor_args: list[str],
):
    """Compute the address of a contract deployed w/ CreateX"""

    try:
        createx = CreateX()

    except RuntimeError:
        createx = CreateX.inject()

    click.echo(
        createx.compute_address(
            contract_type,
            *constructor_args,
            create_type=create_type,
            nonce=nonce,
            salt=salt,
            sender_address=(deployer.address if sender_protection else ZERO_ADDRESS),
            sender_protection=sender_protection,
            redeploy_protection=redeploy_protection,
        )
    )


@cli.command(cls=ConnectedProviderCommand)
@click.option(
    "--type",
    "create_type",
    type=CreationType,
    default=CreationType.CREATE2,
)
@click.option(
    "--leading-zeros",
    default=None,
    type=int,
    help="Number of empty bytes in front of address",
)
@click.option(
    "--max-iterations",
    type=int,
    default=5000,
    help="Max number of cycles to try (default: 5,000).",
)
@account_option("--deployer", prompt="Account to deploy with")
@click.option("--sender-protection/--no-sender-protection", default=True)
@click.option("--redeploy-protection/--no-redeploy-protection", default=True)
@click.argument("contract_type", metavar="CONTRACT", callback=get_contract_type)
@click.argument("constructor_args", metavar="ARGS", nargs=-1)
def mine(
    create_type: CreationType,
    leading_zeros: int | None,
    max_iterations: int,
    deployer: "AccountAPI",
    sender_protection: bool,
    redeploy_protection: bool,
    contract_type: "ContractContainer",
    constructor_args: list[str],
):
    """Mine for an address meeting conditions when deployed w/ CreateX"""

    if leading_zeros is not None:
        if leading_zeros <= 0:
            raise click.BadOptionUsage(
                option_name="leading_zeros",
                message="Cannot be less than 1",
            )

        elif leading_zeros > 8:
            warnings.warn("`--leading-zeros` greater than 8 will likely not converge.")

        def conditions_met(address: "AddressType"):
            return max(to_canonical_address(address)[:leading_zeros]) == 0

    else:
        raise click.UsageError("Must use one of: --leading-zeros")

    try:
        createx = CreateX()

    except RuntimeError:
        createx = CreateX.inject()

    # NOTE: This makes it non-deterministic
    salt = random.randbytes(11)

    iterations = 0
    while not conditions_met(
        address := createx.compute_address(
            contract_type,
            *constructor_args,
            create_type=create_type,
            salt=salt,
            sender_address=(deployer.address if sender_protection else ZERO_ADDRESS),
            redeploy_protection=redeploy_protection,
        )
    ):
        if iterations >= max_iterations:
            raise RuntimeError(f"Could not find solution in {iterations} iterations.")

        salt = to_canonical_address(address)[:11]
        iterations += 1

    click.echo(
        f"Found '{address}' after {iterations} iterations using salt: {salt.hex()}"
    )


@cli.command(cls=ConnectedProviderCommand)
@click.option("--type", "create_type", type=CreationType, default=CreationType.CREATE2)
@click.option("--salt", callback=convert_salt, default=None)
@account_option("--deployer", prompt="Account to deploy with")
@click.option("--sender-protection/--no-sender-protection", default=True)
@click.option("--redeploy-protection/--no-redeploy-protection", default=True)
@click.argument("contract_type", metavar="CONTRACT", callback=get_contract_type)
@click.argument("constructor_args", metavar="ARGS", nargs=-1)
def deploy(
    create_type: CreationType,
    salt: "HexBytes | str | None",
    deployer: "AccountAPI",
    sender_protection: bool,
    redeploy_protection: bool,
    contract_type: "ContractContainer",
    constructor_args: list[str],
):
    """Deploy a contract from your project w/ CreateX"""

    try:
        createx = CreateX()

    except RuntimeError:
        createx = CreateX.inject()

    contract = createx.deploy(
        contract_type,
        *constructor_args,
        create_type=create_type,
        salt=salt,
        # refund=deployer,
        deployment_payable_value=0,
        initialization_payable_value=0,
        sender_protection=sender_protection,
        redeploy_protection=redeploy_protection,
        sender=deployer,
    )
    click.secho(f"Deployed {contract}", fg="green")
