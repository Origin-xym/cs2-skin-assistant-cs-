"""平台采集适配器。

每个平台一个模块，全部继承 base.MarketCollector：

    buff.py     网易 BUFF
    youpin.py   悠悠有品
    c5.py       C5GAME

新增平台 = 新增一个文件 + 实现三个方法，核心链路不需要改动。
"""
