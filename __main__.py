def ismaya():
    try:
        import maya.cmds
    except:
        return False
    return True

if __name__ == "__main__":
    if ismaya():
        from src._main import bundleMain
        bundleMain()
    else:
        pass
