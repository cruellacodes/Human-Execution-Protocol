from setuptools import setup, find_packages

setup(
    name="hxp",
    version="0.1.0",
    description="Human Execution Protocol — Python SDK",
    long_description=open("README.md").read() if __import__("os").path.exists("README.md") else "",
    long_description_content_type="text/markdown",
    author="HXP Protocol",
    url="https://github.com/your-org/hxp",
    packages=["hxp"],
    python_requires=">=3.8",
    install_requires=[
        "httpx>=0.24.0",
        "websockets>=11.0",
    ],
    extras_require={
        "dev": ["pytest", "pytest-asyncio"],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
    ],
)
