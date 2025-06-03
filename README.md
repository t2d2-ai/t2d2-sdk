# T2D2 SDK

A Python SDK for seamless integration with the T2D2 platform.

Easily manage projects, assets, and AI-powered inspections for structural health monitoring.

## Description

**T2D2 SDK** is a Python wrapper for the T2D2 API, enabling seamless integration with T2D2 projects and related assets for structural inspection data management.

- Manage projects, images, annotations, drawings, videos, reports, and more
- Upload, download, and organize assets
- Run AI inference and summarize inspection data
- Integrate with T2D2's web platform

## Documentation

Full documentation is available at: [https://t2d2-ai.github.io/t2d2-sdk/](https://t2d2-ai.github.io/t2d2-sdk/)

## Table of Contents
- [Features](#features)
- [Installation](#installation)
- [Quickstart](#quickstart)
- [Usage](#usage)
- [Contributing](#contributing)
- [License](#license)
- [Support](#support)

## Features

- **Authentication**: API key or email/password
- **Project Management**: Set, get, and summarize projects
- **Asset Management**: Upload/download images, drawings, videos, 3D models, and reports
- **Annotations**: Add, retrieve, and manage annotation classes and annotations
- **Regions & Tags**: Organize assets by regions and tags
- **AI Integration**: Run AI inference on images using project models
- **Summarization**: Summarize images and annotation conditions
- **Notifications**: Send notifications to users or Slack

## Installation

Install the latest version from PyPI:

```bash
pip install --upgrade t2d2-sdk
```

## Quickstart

1. **Sign up for a T2D2 account:** [Register here](https://app.t2d2.ai/auth/register)
2. **Get your API key** from the T2D2 web app
3. **Initialize the client:**

```python
from t2d2_sdk import T2D2

credentials = {'api_key': '<YOUR_API_KEY>'}
t2d2 = T2D2(credentials)
```

## Usage

### Set Project
```python
t2d2.set_project('<PROJECT_ID>')
project_info = t2d2.get_project_info()
print(project_info)
```

### Upload Images
```python
image_paths = ['./images/img1.jpg', './images/img2.jpg']
response = t2d2.upload_images(image_paths)
print(response)
```

### Get Images
```python
images = t2d2.get_images()
for img in images:
    print(img['filename'], img['id'])
```

### Add Annotation Class
```python
result = t2d2.add_annotation_class('Crack', color='#FF0000', materials=['Concrete'])
print(result)
```

### Add Annotations to an Image
```python
annotations = [
    {
        'annotation_class_id': 'class_id',
        'coordinates': [[100, 100], [200, 100], [200, 200], [100, 200]],
        'attributes': {'severity': 'high'}
    }
]
result = t2d2.add_annotations('image_id', annotations)
print(result)
```

### Run AI Inference
```python
result = t2d2.run_ai_inferencer(
    image_ids=['image_id1', 'image_id2'],
    model_id='model_id',
    confidence_threshold=0.6
)
print(result)
```

For more advanced usage, see the [full documentation](https://t2d2-ai.github.io/t2d2-sdk/).

## Contributing

Contributions are welcome! Please contact <bhiriyur@t2d2.ai> for more information.

## License

See the LICENSE file for details.

## Support

- Documentation: [https://t2d2-ai.github.io/t2d2-sdk/](https://t2d2-ai.github.io/t2d2-sdk/)
- Email: <bhiriyur@t2d2.ai>
- T2D2 Web: [https://t2d2.ai](https://t2d2.ai)
