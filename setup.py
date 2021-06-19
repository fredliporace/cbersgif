"""Setup cbersgif."""

from setuptools import find_packages, setup

with open("README.md") as f:
    long_description = f.read()

inst_reqs = [
    "Click",
    "numpy",
    "Pillow",
    "aws-sat-api",
    "pyproj",
    "Shapely",
    "imageio",
    "rasterio",
    "requests",
]

extra_reqs = {
    "dev": ["pytest", "pytest-cov", "tox", "pylint", "pre-commit"],
    "test": [
        "pytest"
    ],
    #"deploy": [],
}

setup(
    name="cbersgif",
    version="0.2.0",
    description=u"Animated GIFs from CBERS data on AWS",
    long_description=long_description,
    long_description_content_type="text/markdown",
    python_requires="==3.7.9",
    author=u"Frederico Liporace",
    author_email="liporace@amskepler.com",
    url="https://github.com/fredliporace/cbersgif",
    packages=find_packages(exclude=["tests*"]),
    entry_points="""
    [console_scripts]
    cbersgif=cbersgif.cli.cbersgif:main
""",
    zip_safe=False,
    install_requires=inst_reqs,
    extras_require=extra_reqs,
)
