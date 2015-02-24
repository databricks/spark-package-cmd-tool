from setuptools import setup

setup(
    name='spark-package',
    version=str(spark_package.__version__),
    description="A command line tool for creating Spark Packages and " \
        "generating release distributions",
    author='Burak Yavuz',
    author_email='feedback@spark-packages.org',
    url='https://github.com/databricks/spark-package-cmd-tool',
    license="Apache-2.0",
    packages=['spark_package',
              'spark_package.resources',
              'spark_package.resources.license_temps'],
    scripts = ['bin/spark-package'],
    long_description=open('README.rst').read()
)
