# Overview

[Ape](https://apeworx.io/framework)-based SDK for working with [CreateX](https://createx.rocks).

## Usage

### Command Line

The primary way to use the `createx` package is through the provided CLI.
You can use this command alongside any ape project to deploy your contracts to a deterministic location.

By default, this uses the CreateX library to deploy using `msg.sender` and/or `chainid` redeploy protection,
with a customizable salt:

```sh
$ createx deploy MyContract --deployer my-wallet --no-redeploy-protection --salt my-salt
INFO:     Confirmed 0xc5af...6c2c (total fees paid = 1838467000000000)
Deployed 0x02168191c1BbBEc53c6b7c1b5Ed0ddf83D76A837
```

For more info, check out [here](https://github.com/pcaversaccio/createx/tree/main?tab=readme-ov-file#permissioned-deploy-protection-and-cross-chain-redeploy-protection).

We also provide a utility for "mining" an address using a specific number of leading zeros, or matching a pattern
(similar to [createXcrunch](https://github.com/HrikB/createXcrunch)):

```sh
$ createx mine dep@v1:MyContract --deployer ... --leading-zeros 1
Found '0x0082fA6c17B8A25F99d60513b8683434666a7C44' after 835 iterations using salt: 184d662996b122cf1846c7
```

You can then re-use this salt to get the same value on multiple chains:

```sh
$ createx address dep@v1:MyContract --deployer ... --salt 184d662996b122cf1846c7
0x0082fA6c17B8A25F99d60513b8683434666a7C44

$ createx deploy dep@v1:MyContract --deployer ... --salt 184d662996b122cf1846c7
INFO:     Confirmed 0x54f6...bd26 (total fees paid = 1838419000000000)
Deployed 0x0082fA6c17B8A25F99d60513b8683434666a7C44
```

### As a Library

You can also use this in your projects to configure deterministic deployments more easily on CreateX's 170+ supported chains:

```py
from createx import CreateX

my_contract = createx.deploy(project.MyContract, salt="something", sender=me)
```
