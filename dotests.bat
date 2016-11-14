@echo off
REM @set PYTHONPATH=D:\talha.ahmed\workspace\pyenv_common;%PYTHONPATH%
@REM test test_ui*
@"C:\Program Files\Autodesk\Maya2015\bin\mayapy.exe" -m unittest discover -s test test_main.py
