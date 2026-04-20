import pandas as pd

from leadlag.portfolio.weights import long_short_equal_weight


def test_equal_weight_long_short() -> None:
    signal = pd.Series([5, 4, 3, 2, 1], index=list("ABCDE"))
    w = long_short_equal_weight(signal, quantile_q=0.2, allow_short=True)
    assert w["A"] == 1.0
    assert w["E"] == -1.0
