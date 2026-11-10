"""
Strict stand-in for Streamlit used when the real package is not installed.

It does not draw anything; it enforces rules that commonly break real apps:
duplicate explicit keys, duplicate auto-generated widget ids, and calling
widgets with arguments the real API does not accept.
"""
__version__ = "1.52.0"
import pandas as pd


class StopException(Exception):
    pass


class _State(dict):
    __getattr__ = dict.get
    def __setattr__(self, k, v): self[k] = v


session_state = _State()
_RUN = {"keys": set(), "ids": set(), "elements": []}


def reset_run():
    _RUN["keys"].clear(); _RUN["ids"].clear(); _RUN["elements"].clear()


def _register(kind, label, key, extra=""):
    if key is not None:
        if key in _RUN["keys"]:
            raise RuntimeError(f"DuplicateElementKey: {key!r}")
        _RUN["keys"].add(key)
    else:
        ident = (kind, str(label), extra)
        if ident in _RUN["ids"]:
            raise RuntimeError(f"DuplicateWidgetID: {ident}")
        _RUN["ids"].add(ident)


class _Cfg:
    @staticmethod
    def ImageColumn(*a, **k): return ("image", a, k)
    @staticmethod
    def NumberColumn(*a, **k): return ("number", a, k)


column_config = _Cfg


class _Api:
    def __init__(self): self.sidebar_calls = 0
    def __enter__(self): return self
    def __exit__(self, *a): return False

    # layout
    def columns(self, spec, **k): n = spec if isinstance(spec, int) else len(spec); return [_Api() for _ in range(n)]
    def tabs(self, labels): return [_Api() for _ in labels]
    def container(self, **k): return _Api()
    def expander(self, *a, **k): return _Api()
    def empty(self): return _Api()

    # text
    def markdown(self, body, **k): _RUN["elements"].append(("md", body)); return None
    def caption(self, *a, **k): return None
    def error(self, msg, **k): _RUN["elements"].append(("error", str(msg)))
    def warning(self, msg, **k): _RUN["elements"].append(("warning", str(msg)))
    def code(self, *a, **k): return None
    def write(self, *a, **k): return None
    def stop(self): raise StopException()
    def image(self, path, **k):
        import os
        assert os.path.exists(str(path)), f"image not found: {path}"
    # data display
    def plotly_chart(self, fig, key=None, **k):
        assert hasattr(fig, "traces"), "plotly_chart expects a Figure"
        assert not ({"use_container_width", "width"} == set(k) & {"use_container_width", "width"}), "pass only one width option"
        _register("plotly", "plotly", key)
        _RUN["elements"].append(("plot", fig))
    def dataframe(self, df, **k):
        assert isinstance(df, pd.DataFrame), "dataframe expects a DataFrame"
        _RUN["elements"].append(("table", df))
    def download_button(self, label, data, file_name=None, mime=None, key=None, **k):
        assert isinstance(data, (bytes, str)), "download data must be bytes/str"
        _register("download", label, key, file_name); return False
    def button(self, label, key=None, on_click=None, **k):
        _register("button", label, key); return bool(session_state.get("_click_" + str(key)))

    # inputs (return stored value or a sensible default)
    def _pick(self, kind, label, key, options, default, **k):
        _register(kind, label, key, str(list(options))[:80])
        return session_state.get(key, default) if key else default
    def radio(self, label, options, key=None, **k):
        options = list(options); return self._pick("radio", label, key, options, options[0])
    def selectbox(self, label, options, key=None, **k):
        options = list(options); v = self._pick("select", label, key, options, options[0] if options else None)
        if key and options and v not in options:
            v = options[0]
        return v
    def multiselect(self, label, options, key=None, **k): return self._pick("multi", label, key, list(options), [])
    def text_input(self, label, key=None, **k): return self._pick("text", label, key, [], "")
    def text_area(self, label, value="", key=None, **k): return self._pick("area", label, key, [], value)
    def date_input(self, label, value=None, key=None, **k): return self._pick("date", label, key, [], value)

    @property
    def sidebar(self): return _Api()


_root = _Api()
for _n in dir(_root):
    if not _n.startswith("_") and _n != "sidebar":
        globals()[_n] = getattr(_root, _n)
sidebar = _Api()


def set_page_config(**k): return None


def cache_data(*a, **k):
    if a and callable(a[0]): return a[0]
    return lambda f: f


cache_resource = cache_data


class _Secrets:
    def get(self, *a, **k): raise FileNotFoundError("no secrets")
secrets = _Secrets()
from . import components  # noqa: E402,F401
