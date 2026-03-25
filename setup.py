from setuptools import setup, find_packages

setup(
    name="homeassistant-historical-sensor-patch",  # nombre del paquete en PyPI
    version="2.0.0.dev1",                         # tu versión
    description="Fork parcheado de homeassistant-historical-sensor",
    url="https://github.com/monforte10/ha-historical-sensor-patch",
    author="Tu Nombre",
    author_email="tuemail@example.com",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[],   # si hay dependencias externas, agrégalas aquí
)
