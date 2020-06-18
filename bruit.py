#!/usr/bin/python3
import sys
import json
import urllib
import pathlib
import hashlib
from collections import defaultdict
import random

import numpy as np
from urllib.parse import urlencode
from urllib.request import urlopen, urlretrieve

if len(sys.argv) > 1:
    RUN_NAME = sys.argv[-1]
else:
    RUN_NAME = "test-windows7-32/opt-raptor-tp6-8-firefox-e10s"

AD_QUERY = {
    "from": "perf",
    "select": [
        "run.name",
        "run.timestamp",
        "result.suite",
        "result.test",
        "result.samples",
        "result.stats",
        "result.tags"
    ],
    "where": {
        "and": [
            {"gte": {"action.start_time": {"date": "today-6month"}}},
            {"lt": {"action.start_time": {"date": "today"}}},
            {
                "or": [
                    {"find": {"run.name": "raptor"}},
               #     {"find": {"run.name": "browsertime"}},
                ]
            },
            {"or": [{"find": {"run.name": RUN_NAME}},
                ]},
            {"eq": {"task.state": "completed"}},
            {"eq":{"result.test":"loadtime"}},
            {"eq": {"build.branch": "mozilla-central"}},
            {"eq":{"result.suite":"raptor-tp6-wikipedia-firefox"}}
        ]
    },
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

    response = urllib.request.urlopen(req, jsondataasbytes)
    data = response.read().decode("utf8").replace("'", '"')
    with saved.open("w") as f:
        f.write(data)
    return json.loads(data)["data"]


# Set the number of data points to look at
AD_QUERY["limit"] = 100000

data = query_activedata(AD_QUERY)
failed = 0

def _progressive(samples, threshold=2.8):
    global failed
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
    failed += 1
    return np.median(samples), i, perm

size = 25
dump = 2
tot = size - dump
res = defaultdict(list)
for c, task in enumerate(data["run.name"]):
    ts = data["run.timestamp"][c]
    test = data["result.test"][c]
    samples = data["result.samples"][c]
    if not samples or not isinstance(samples, list):
        # Some tests are missing these
        continue
    if len(samples) < size:
        continue
    # removing the first one
    samples = samples[dump:]
    random.shuffle(samples)

    res[task].append(
        {
            "original": np.median(samples),
            "with_8": np.median(samples[:8]),
            "with_13": np.median(samples[:13]),
            "with_20": np.median(samples[:20]),
            "progressive": _progressive(samples),
            "ts": ts,
            "samples": samples
        }
    )


def diff(orig, new):
    return (new - orig) / orig * 100


occ  = defaultdict(int)
avg = {"8": [], "13": [], "20": [], "prog": []}
big = 0
total = 0
rn = ",".join([str(i) for i in range(tot)])
print("name,when,24,20,20_diff,13,13_diff,8,8_diff,prog,prog_diff,prog_samples,prog_perms,"+rn)
for name, values in res.items():
    #print(name)
    for value in values:
        #m = (
        #    "\twhen %s\n"
        #    "\t25 samples: %.2f\n"
        #    "\t20 samples: %.2f (%.2f%%)\n"
        #    "\t13 samples: %.2f (%.2f%%)\n"
        #    "\t8 samples: %.2f (%.2f%%)\n"
        #    "\tprogressive %.2f (%.2f%%) (%d samples, %d perms)"
        #)
        m = "%s,%s,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%d,%d"

        prog, samp, perm = value["progressive"]
        orig = value["original"]
        with_13 = value["with_13"]
        with_13_diff = diff(orig, with_13)
        prog_diff = diff(orig, prog)
        if with_13_diff > 10:
            big += 1
        total += 1
        with_20 = value["with_20"]
        with_8 = value["with_8"]
        with_8_diff = diff(orig, with_8)
        with_20_diff = diff(orig, with_20)
        m =  m % (
                name,
                value["ts"],
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
        m += "," + ",".join([str(v) for v in value["samples"]])
        print(m)
        #avg["8"].append(with_8_diff)
        #avg["13"].append(with_13_diff)
        #avg["20"].append(with_20_diff)
        #avg["prog"].append(prog_diff)
        occ[name] += 1

#print("8 samples average diff %.2f%%" % np.average(avg["8"]))
#print("13 samples average diff %.2f%%" % np.average(avg["13"]))
#print("20 samples average diff %.2f%%" % np.average(avg["20"]))
#print("progressive samples diff %.2f%%" % np.average(avg["prog"]))
#print("Failed " + str(failed))
#print("Too big " + str(big))
#print("Total " + str(total))

#print(sorted([(num, n) for n, num in occ.items()]))

