# T2D2 Python SDK

## Description

T2D2 SDK python wrapper to API to interface with T2D2 projects and related assets.

## Table of Contents

- [T2D2 Python SDK](#t2d2-python-sdk)
  - [Description](#description)
  - [Table of Contents](#table-of-contents)
  - [Installation](#installation)
  - [Usage](#usage)
  - [Contributing](#contributing)
  - [License](#license)

## Installation

This SDK is published to PyPI and the latest version can be installed as follows:
`pip install --upgrade t2d2-sdk`

## Usage

These instructions assume that you have an account at T2D2 (<https://t2d2.ai>). If you do not have an account, you can sign up here: (<https://app.t2d2.ai/auth/register>). Subscription pricing details may be found here: (<https://t2d2.ai/pricing>).

Once you have an account created, you can either use your email/password or an _API KEY_ to instantiate the T2D2 client.

```python
from t2d2_sdk import T2D2

credentials = {'email': "my@email.com", 'password': "<MYPASSWORD>"}
credentials = {'api_key': "<MY_API_KEY>"}

t2d2 = T2D2(credentials)
```

With this client, you can interface with the app and get access to most of the features of the web interface. More documentation coming soon at <https://docs.t2d2.ai>.

```python
t2d2.set_project(PROJECT_ID)
project = t2d2.get_project()
data = t2d2.get_images()
...
```

## Contributing

Please contact <bhiriyur@t2d2.ai> for further information on contributing to this project.

## License

Information about the project's license.
