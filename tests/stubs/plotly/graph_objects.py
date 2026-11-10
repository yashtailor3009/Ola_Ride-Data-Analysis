"""
Strict stub of ``plotly.graph_objects``.

It records figures and **validates property names** against whitelists of the
properties the project is allowed to use, so a typo (e.g. ``textpostion``)
raises ValueError exactly like the real library would.
"""
TRACE_PROPS = {
    "Bar": {"x", "y", "name", "marker", "marker_color", "marker_line", "opacity", "text", "textposition", "cliponaxis",
            "hovertemplate", "orientation", "customdata", "insidetextanchor", "textfont", "hoverinfo", "showlegend", "offsetgroup"},
    "Scatter": {"x", "y", "mode", "name", "line", "marker", "yaxis", "hovertemplate", "text", "textposition", "opacity", "showlegend"},
    "Scattergl": {"x", "y", "mode", "marker", "name", "hovertemplate"},
    "Pie": {"labels", "values", "hole", "sort", "direction", "marker", "textinfo", "textfont", "hovertemplate"},
    "Box": {"x", "y", "q1", "median", "q3", "lowerfence", "upperfence", "mean", "marker_color", "fillcolor", "line",
            "boxmean", "name", "showlegend"},
    "Heatmap": {"z", "x", "y", "colorscale", "zmin", "zmax", "showscale", "text", "texttemplate", "textfont", "hovertemplate"},
}
LAYOUT_PROPS = {"height", "paper_bgcolor", "plot_bgcolor", "font", "margin", "showlegend", "legend", "hoverlabel", "barmode",
                "bargap", "hovermode", "xaxis", "yaxis", "yaxis2", "width", "title"}
AXIS_PROPS = {"showgrid", "linecolor", "tickfont", "automargin", "gridcolor", "zeroline", "title", "rangemode", "range", "dtick",
              "type", "tickformat", "side", "overlaying", "tickangle", "visible", "autorange"}
ANNOT_PROPS = {"xref", "yref", "x", "y", "text", "showarrow", "align", "xanchor", "yanchor", "bgcolor", "bordercolor",
               "borderwidth", "borderpad", "font", "arrowhead", "arrowwidth", "arrowcolor", "ax", "ay"}
LINE_PROPS = {"y", "x", "line_dash", "line_color", "line_width"}


def _check(kind, kwargs, allowed):
    bad = set(kwargs) - allowed
    if bad:
        raise ValueError(f"Invalid {kind} properties: {sorted(bad)}")


def _check_len(trace):
    """x/y length mismatches are a common silent bug - fail loudly in tests."""
    x, y = trace.props.get("x"), trace.props.get("y")
    try:
        if x is not None and y is not None and len(x) != len(y) and trace.kind != "Heatmap":
            raise ValueError(f"{trace.kind}: len(x)={len(x)} != len(y)={len(y)}")
    except TypeError:
        pass


class _Trace:
    def __init__(self, kind, **kwargs):
        _check(f"{kind} trace", kwargs, TRACE_PROPS[kind])
        self.kind, self.props = kind, kwargs
        _check_len(self)


def _make(kind):
    return lambda **kw: _Trace(kind, **kw)


Bar, Scatter, Scattergl, Pie, Box, Heatmap = (_make(k) for k in ("Bar", "Scatter", "Scattergl", "Pie", "Box", "Heatmap"))


class Figure:
    def __init__(self, data=None, layout=None):
        self.traces, self.annotations, self.layout = [], [], {}
        if data is not None:
            self.traces.append(data)

    # trace helpers -----------------------------------------------------
    def add_trace(self, t): self.traces.append(t); return self
    def add_bar(self, **kw): self.traces.append(_Trace("Bar", **kw)); return self
    def add_scatter(self, **kw): self.traces.append(_Trace("Scatter", **kw)); return self

    # layout ------------------------------------------------------------
    def update_layout(self, **kw):
        _check("layout", kw, LAYOUT_PROPS)
        for k in ("xaxis", "yaxis", "yaxis2"):
            if k in kw:
                _check(k, kw[k], AXIS_PROPS)
        self.layout.update(kw); return self

    def update_xaxes(self, **kw): _check("xaxis", kw, AXIS_PROPS); return self
    def update_yaxes(self, **kw): _check("yaxis", kw, AXIS_PROPS); return self
    def add_annotation(self, **kw): _check("annotation", kw, ANNOT_PROPS); self.annotations.append(kw); return self
    def add_hline(self, **kw): _check("hline", kw, LINE_PROPS); return self
    def add_vline(self, **kw): _check("vline", kw, LINE_PROPS); return self
