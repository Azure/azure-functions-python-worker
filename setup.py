from setuptools import setup


setup(
    name='azure',
    version='0.0.1',
    description='Azure Python Functions',
    classifiers=[
        'License :: OSI Approved :: MIT License',
        'Intended Audience :: Developers',
        'Programming Language :: Python :: 3',
        'Operating System :: Microsoft :: Windows',
        'Operating System :: POSIX',
        'Operating System :: MacOS :: MacOS X',
        'Environment :: Web Environment',
        'Development Status :: 3 - Alpha',
    ],
    license='MIT',
    packages=['azure', 'azure.worker', 'azure.functions'],
    provides=['azure'],
    include_package_data=True,
)
