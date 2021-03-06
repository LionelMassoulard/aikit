# -*- coding: utf-8 -*-
"""
Created on Fri Sep 14 12:01:47 2018

@author: Lionel Massoulard
"""

import pandas as pd
import numpy as np

from tests.helpers.testing_help import get_sample_df
from aikit.transformers.target import TargetEncoderClassifier, TargetEncoderEntropyClassifier, TargetEncoderRegressor


def test_loc_align():
    # Test to prevent from a change in pandas behavior
    s1 = pd.Series([10, 11, 12], index=[1, 2, 3])
    s2 = pd.Series(data=0, index=[0, 1, 2])

    inter = np.intersect1d(s2.index, s1.index)

    s2.loc[inter] = s1.loc[inter]

    assert list(s2.values) == [0, 10, 11]


def test_TargetEncoderRegressor():
    df = get_sample_df(100)
    df["cat_col"] = df["text_col"].apply(lambda s: s[0:3])
    np.random.seed(123)
    y = np.random.randn(100)

    for cv in (None, 10):
        for noise_level in (None, 0.1):

            encoder = TargetEncoderRegressor(noise_level=noise_level, cv=cv)
            encoder.fit(df, y)
            res = encoder.transform(df)

            assert encoder.get_feature_names() == ["float_col", "int_col", "text_col", "cat_col__target_mean"]
            assert list(res.columns) == ["float_col", "int_col", "text_col", "cat_col__target_mean"]
            assert res["cat_col__target_mean"].isnull().sum() == 0
            assert (res.index == df.index).all()
            assert encoder.model._columns_to_encode == ["cat_col"]
            assert encoder.model._columns_to_keep == ["float_col", "int_col", "text_col"]

            temp = pd.DataFrame({"cat_col": df["cat_col"], "cat_col__target_mean": res["cat_col__target_mean"]})
            assert temp.groupby("cat_col")["cat_col__target_mean"].std().max() == 0

            encoder = TargetEncoderRegressor(noise_level=noise_level, cv=cv)
            res = encoder.fit_transform(df, y)

            assert encoder.get_feature_names() == ["float_col", "int_col", "text_col", "cat_col__target_mean"]
            assert list(res.columns) == ["float_col", "int_col", "text_col", "cat_col__target_mean"]
            assert res["cat_col__target_mean"].isnull().sum() == 0
            assert (res.index == df.index).all()
            assert encoder.model._columns_to_encode == ["cat_col"]
            assert encoder.model._columns_to_keep == ["float_col", "int_col", "text_col"]


def test_TargetEncoderClassifier():
    df = get_sample_df(100)
    df["cat_col"] = df["text_col"].apply(lambda s: s[0:3])

    np.random.seed(123)
    y = 1 * (np.random.randn(100) > 0)

    for cv in (None, 10):
        for noise_level in (None, 0.1):

            encoder = TargetEncoderClassifier(noise_level=noise_level, cv=cv)
            encoder.fit(df, y)
            res = encoder.transform(df)

            assert encoder.get_feature_names() == ["float_col", "int_col", "text_col", "cat_col__target_1"]
            assert list(res.columns) == ["float_col", "int_col", "text_col", "cat_col__target_1"]
            assert res["cat_col__target_1"].isnull().sum() == 0
            assert res["cat_col__target_1"].isnull().max() <= 1
            assert res["cat_col__target_1"].isnull().min() >= 0

            temp = pd.DataFrame({"cat_col": df["cat_col"], "cat_col__target_1": res["cat_col__target_1"]})
            assert temp.groupby("cat_col")["cat_col__target_1"].std().max() == 0

            assert (res.index == df.index).all()
            assert encoder.model._columns_to_encode == ["cat_col"]
            assert encoder.model._columns_to_keep == ["float_col", "int_col", "text_col"]

            encoder = TargetEncoderClassifier(noise_level=noise_level, cv=cv)
            res = encoder.fit_transform(df, y)

            assert encoder.get_feature_names() == ["float_col", "int_col", "text_col", "cat_col__target_1"]
            assert list(res.columns) == ["float_col", "int_col", "text_col", "cat_col__target_1"]

            assert res["cat_col__target_1"].isnull().sum() == 0
            assert res["cat_col__target_1"].isnull().max() <= 1
            assert res["cat_col__target_1"].isnull().min() >= 0

            assert (res.index == df.index).all()
            assert encoder.model._columns_to_encode == ["cat_col"]
            assert encoder.model._columns_to_keep == ["float_col", "int_col", "text_col"]

    np.random.seed(123)
    y = np.array(["aa", "bb", "cc"])[np.random.randint(0, 3, size=100)]

    for cv in (None, 10):
        for noise_level in (None, 0.1):

            encoder = TargetEncoderClassifier(noise_level=noise_level, cv=cv)
            encoder.fit(df, y)
            res = encoder.transform(df)

            assert encoder.get_feature_names() == [
                "float_col",
                "int_col",
                "text_col",
                "cat_col__target_aa",
                "cat_col__target_bb",
                "cat_col__target_cc",
            ]
            assert list(res.columns) == [
                "float_col",
                "int_col",
                "text_col",
                "cat_col__target_aa",
                "cat_col__target_bb",
                "cat_col__target_cc",
            ]

            for col in ("cat_col__target_aa", "cat_col__target_bb", "cat_col__target_cc"):
                assert res[col].isnull().sum() == 0
                assert res[col].isnull().max() <= 1
                assert res[col].isnull().min() >= 0

                temp = pd.DataFrame({"cat_col": df["cat_col"], col: res[col]})
                assert temp.groupby("cat_col")[col].std().max() == 0

            assert encoder.model._columns_to_encode == ["cat_col"]
            assert encoder.model._columns_to_keep == ["float_col", "int_col", "text_col"]
            assert (res.index == df.index).all()

            encoder = TargetEncoderClassifier(noise_level=noise_level, cv=cv)
            res = encoder.fit_transform(df, y)

            assert encoder.get_feature_names() == [
                "float_col",
                "int_col",
                "text_col",
                "cat_col__target_aa",
                "cat_col__target_bb",
                "cat_col__target_cc",
            ]
            assert list(res.columns) == [
                "float_col",
                "int_col",
                "text_col",
                "cat_col__target_aa",
                "cat_col__target_bb",
                "cat_col__target_cc",
            ]
            for col in ("cat_col__target_aa", "cat_col__target_bb", "cat_col__target_cc"):
                assert res[col].isnull().sum() == 0
                assert res[col].isnull().max() <= 1
                assert res[col].isnull().min() >= 0
            assert (res.index == df.index).all()
            assert encoder.model._columns_to_encode == ["cat_col"]
            assert encoder.model._columns_to_keep == ["float_col", "int_col", "text_col"]


def test_TargetEncoderEntropyClassifier():
    df = get_sample_df(100)
    df["cat_col"] = df["text_col"].apply(lambda s: s[0:3])

    np.random.seed(123)
    y = 1 * (np.random.randn(100) > 0)

    for cv in (None, 10):
        for noise_level in (None, 0.1):

            encoder = TargetEncoderEntropyClassifier(noise_level=noise_level, cv=cv)
            encoder.fit(df, y)
            res = encoder.transform(df)

            assert encoder.get_feature_names() == ["float_col", "int_col", "text_col", "cat_col__target_entropy"]
            assert list(res.columns) == ["float_col", "int_col", "text_col", "cat_col__target_entropy"]
            assert res["cat_col__target_entropy"].isnull().sum() == 0
            assert res["cat_col__target_entropy"].isnull().min() >= 0
            temp = pd.DataFrame({"cat_col": df["cat_col"], "cat_col__target_entropy": res["cat_col__target_entropy"]})
            assert temp.groupby("cat_col")["cat_col__target_entropy"].std().max() == 0

            assert encoder.model._columns_to_encode == ["cat_col"]
            assert encoder.model._columns_to_keep == ["float_col", "int_col", "text_col"]
            assert (res.index == df.index).all()

            encoder = TargetEncoderEntropyClassifier(noise_level=noise_level, cv=cv)
            res = encoder.fit_transform(df, y)

            assert encoder.get_feature_names() == ["float_col", "int_col", "text_col", "cat_col__target_entropy"]
            assert list(res.columns) == ["float_col", "int_col", "text_col", "cat_col__target_entropy"]
            assert res["cat_col__target_entropy"].isnull().sum() == 0
            assert res["cat_col__target_entropy"].isnull().min() >= 0
            assert (res.index == df.index).all()
            assert encoder.model._columns_to_encode == ["cat_col"]
            assert encoder.model._columns_to_keep == ["float_col", "int_col", "text_col"]


def verif_all():
    test_loc_align()
    test_TargetEncoderClassifier()
    test_TargetEncoderEntropyClassifier()
    test_TargetEncoderRegressor()
