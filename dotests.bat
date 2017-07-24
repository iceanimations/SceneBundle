@echo off
REM @set PYTHONPATH=D:\talha.ahmed\workspace\pyenv_common;%PYTHONPATH%

REM @"C:\Program Files\Autodesk\Maya2015\bin\mayapy.exe" -m unittest discover test test_process*
REM @"C:\Program Files\Autodesk\Maya2015\bin\mayapy.exe" -m unittest discover test test_main*
REM @"C:\Program Files\Autodesk\Maya2015\bin\mayapy.exe" -m unittest discover test test_bundle*

@"C:\Program Files\Autodesk\Maya2016\bin\mayapy.exe" -m unittest -v test.test_process test.test_bundle test.test_main test.test_ui
