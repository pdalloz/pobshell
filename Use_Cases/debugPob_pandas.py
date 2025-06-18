import sys
from sklearn import datasets
import pandas as pd

from sklearn.datasets import load_iris
iris = load_iris(as_frame=True)
df = pd.DataFrame({"x": [1, 2, 3, 4], "y": ["a", "b", "b", "c"]})
df["y"] = pd.Categorical(df["y"], categories=["a", "b", "c"], ordered=True)
ci = pd.CategoricalIndex(df["y"])

# breakpoint()
import pobshell; pobshell.shell()

# pob.shell(iris)
# breakpoint()
# pob.shell()
print('Bye!')
