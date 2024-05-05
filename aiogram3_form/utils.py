import functools
import inspect
from typing import Callable


def prepare_function(func: Callable, *args, **kwargs):
    arg_spec = inspect.getfullargspec(func)

    prepared_kwargs = {
        k: v
        for k, v in kwargs.items()
        if k in arg_spec.args or k in arg_spec.kwonlyargs
    }

    partial_func = functools.partial(func, *args, **prepared_kwargs)
    return partial_func
