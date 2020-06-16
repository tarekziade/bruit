#!/usr/bin/python3
import json
import urllib
import pathlib
import hashlib
from collections import defaultdict

import numpy as np
from urllib.parse import urlencode
from urllib.request import urlopen, urlretrieve

"""
Modify the `find` fields to change the tasks that
you analyze data from.

If you want data from a certain period use:
    {"gte": {"date": "today-20day"}},
    {"lt": {"date": "today"}},

"""
AD_QUERY = {
    "from": "perf",
    "where": {
        "and": [
            {
                "or": [
                    {"find": {"run.name": "raptor"}},
                    {"find": {"run.name": "browsertime"}},
                ]
            },
            {"or": [{"find": {"run.name": "tp6-"}}, {"find": {"run.name": "tp6m-"}}]},
            {"eq": {"task.state": "completed"}},
        ]
    },
    "select": [
        "run.name",
        "result.suite",
        "result.test",
        "result.samples",
        "result.stats",
    ],
    "limit": 1,
}


def query_activedata(query_json):
    """
    Used to run queries on active data.
    """
    hash = json.dumps(query_json, sort_keys=True, indent=2)
    hash = hashlib.md5(hash.encode("utf8")).hexdigest()
    saved = pathlib.Path(hash + ".cached")
    if saved.exists():
        with saved.open() as f:
            return json.loads(f.read())["data"]

    active_data_url = "http://activedata.allizom.org/query"

    req = urllib.request.Request(active_data_url)
    req.add_header("Content-Type", "application/json")
    jsondata = json.dumps(query_json)

    jsondataasbytes = jsondata.encode("utf-8")
    req.add_header("Content-Length", len(jsondataasbytes))

    print("Querying Active-data...")
    response = urllib.request.urlopen(req, jsondataasbytes)
    print("Status:" + str(response.getcode()))
    data = response.read().decode("utf8").replace("'", '"')
    with saved.open("w") as f:
        f.write(data)
    return json.loads(data)["data"]


# Set the number of data points to look at
AD_QUERY["limit"] = 10000
data = query_activedata(AD_QUERY)


def _progressive(samples, threshold=2):
    # starts with 9
    data = samples[:9]
    i = 8
    perm = 0
    while i < len(samples):
        z_scores = np.abs((data - np.median(data)) / np.std(data))
        outliers = np.where(z_scores > threshold)[0]
        if len(outliers) == 0:
            return np.median(data), i, perm
        new = len(outliers)
        data = [e for i, e in enumerate(data) if i not in outliers]
        for e in range(new):
            if i >= len(samples):
                return np.median(samples), i, perm
            data.append(samples[i])
            perm += 1
            i += 1
    return np.median(samples), i, perm


res = defaultdict(list)

for c, task in enumerate(data["run.name"]):
    test = data["result.test"][c]
    samples = data["result.samples"][c]
    if not samples:
        # Some tests are missing these
        continue
    if len(samples) < 25:
        continue
    res[task].append(
        {
            "original": np.median(samples),
            "with_8": np.median(samples[:8]),
            "with_13": np.median(samples[:13]),
            "with_20": np.median(samples[:20]),
            "progressive": _progressive(samples),
        }
    )


def diff(orig, new):
    return (new - orig) / orig * 100


avg = {"8": [], "13": [], "20": [], "prog": []}

for name, values in res.items():
    print(name)
    for value in values:
        m = (
            "\t25 samples: %.2f\n"
            "\t20 samples: %.2f (%.2f%%)\n"
            "\t13 samples: %.2f (%.2f%%)\n"
            "\t8 samples: %.2f (%.2f%%)\n"
            "\tprogressive %.2f (%.2f%%) (%d samples, %d perms)"
        )

        prog, samp, perm = value["progressive"]
        orig = value["original"]
        with_13 = value["with_13"]
        with_13_diff = diff(orig, with_13)
        prog_diff = diff(orig, prog)
        with_20 = value["with_20"]
        with_8 = value["with_8"]
        with_8_diff = diff(orig, with_8)
        with_20_diff = diff(orig, with_20)
        print(
            m
            % (
                orig,
                with_20,
                with_20_diff,
                with_13,
                with_13_diff,
                with_8,
                with_8_diff,
                prog,
                prog_diff,
                samp,
                perm,
            )
        )
        print()
        avg["8"].append(with_8_diff)
        avg["13"].append(with_13_diff)
        avg["20"].append(with_20_diff)
        avg["prog"].append(prog_diff)

print("8 samples average diff %.2f%%" % np.average(avg["8"]))
print("13 samples average diff %.2f%%" % np.average(avg["13"]))
print("20 samples average diff %.2f%%" % np.average(avg["20"]))
print("progressive samples diff %.2f%%" % np.average(avg["prog"]))
