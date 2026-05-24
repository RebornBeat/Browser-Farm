from setuptools import setup, find_packages

setup(
    name="browser-farm",
    version="0.1.0",
    packages=find_packages(where="src"),
    install_requires=[
        "fastapi>=0.109.0",
        "uvicorn[standard]>=0.27.0",
        "playwright>=1.41.0",
        "psutil>=5.9.8",
        "python-multipart>=0.0.6",
        "python-dotenv>=1.0.0",
        "pydantic>=2.5.3",
        "pydantic-settings>=2.1.0",
        "websockets>=12.0",
        "aiofiles>=23.2.1",
        "pillow>=10.2.0",
    ],
    package_dir={"": "src"},
    include_package_data=True,
    entry_points={
        "console_scripts": [
            "browser-farm=browser_farm.server:main"
        ],
    },
)
