from __future__ import annotations


class FinanceConnectorError(RuntimeError):
    pass


class FinanceConnectorDataError(FinanceConnectorError):
    pass
