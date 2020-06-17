from pandas import read_csv
from matplotlib import pyplot
from datetime import datetime
from matplotlib.pylab import plt


def dp(arg):
    return [datetime.fromtimestamp(float(a)) for a in arg]

parse_dates = ["when"]

for s in ("24", "20", "13", "8", "prog"):
    series = read_csv('bruit.csv', header=0, index_col=0,
            squeeze=True, parse_dates=parse_dates,
            date_parser=dp,
            usecols=["when", s])

    series = series.sort_index()
    #series.plot(style='k.')
    #pyplot.show()
    plt.plot(series)
plt.show()

