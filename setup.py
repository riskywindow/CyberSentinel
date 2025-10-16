#!/usr/bin/env python3
"""Setup script for CyberSentinel."""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="cybersentinel",
    version="0.1.0",
    author="CyberSentinel Team",
    author_email="team@cybersentinel.dev",
    description="End-to-end purple-team cyber-defense lab with multi-agent orchestration",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/cybersentinel/cybersentinel",
    packages=find_packages(exclude=["tests", "tests.*", "integration_tests", "integration_tests.*"]),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Intended Audience :: Information Technology",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Security",
        "Topic :: System :: Monitoring",
    ],
    python_requires=">=3.11",
    install_requires=requirements,
    extras_require={
        "dev": [line.strip() for line in open("requirements-dev.txt") 
                if line.strip() and not line.startswith("#")],
        "kafka": ["kafka-python>=2.0.2"],
        "pinecone": ["pinecone-client>=2.2.0"],
        "observability": ["prometheus-client>=0.17.0", "grafana-api>=1.0.3"],
    },
    entry_points={
        "console_scripts": [
            "cybersentinel=scripts.cli:main",
            "cs-replay=scripts.replay:main",
            "cs-eval=scripts.eval:main",
        ],
    },
    include_package_data=True,
    package_data={
        "": ["*.yml", "*.yaml", "*.json", "*.sql", "*.cql", "*.proto", "*.md"],
    },
)