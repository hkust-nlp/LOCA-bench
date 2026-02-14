"""Dynamic class import utility."""

import importlib


def dynamic_import_class(class_path: str):
    """
    Dynamically import a class from a module path.

    Args:
        class_path: Full path to class, e.g., 'gem.envs.canvas_list_test_s2l.canvas_list_test_s2l.CanvasListTestS2LEnv'

    Returns:
        The imported class
    """
    module_path, class_name = class_path.rsplit('.', 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)
