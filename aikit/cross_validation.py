# -*- coding: utf-8 -*-
"""
Created on Thu Aug 23 09:40:33 2018

@author: Lionel Massoulard
"""


import numpy as np
import pandas as pd
import scipy.sparse as sp

from collections import OrderedDict
from time import time
import numbers

import sklearn.model_selection

import sklearn.base

from aikit.tools.helper_functions import function_has_named_argument


def is_clusterer(estimator):
    """Returns True if the given estimator is (probably) a clusterer.
    Parameters
    ----------
    estimator : object
        Estimator object to test.
    Returns
    -------
    out : bool
        True if estimator is a regressor and False otherwise.
    """
    return getattr(estimator, "_estimator_type", None) == "clusterer"


def create_cv(cv=3, y=None, classifier=False, shuffle=False, random_state=None):
    """Input checker utility for building a cross-validator, difference from sklearn.model_selection.check_cv  :

    * shuffle and random_state params


    Parameters
    ----------
    cv : int, cross-validation generator or an iterable, optional
        Determines the cross-validation splitting strategy.
        Possible inputs for cv are:
          - None, to use the default 3-fold cross-validation,
          - integer, to specify the number of folds.
          - An object to be used as a cross-validation generator.
          - An iterable yielding train/test splits.

        For integer/None inputs, if classifier is True and ``y`` is either
        binary or multiclass, :class:`StratifiedKFold` is used. In all other
        cases, :class:`KFold` is used.

        Refer :ref:`User Guide <cross_validation>` for the various
        cross-validation strategies that can be used here.

    y : array-like, optional
        The target variable for supervised learning problems.

    classifier : boolean, optional, default False
        Whether the task is a classification task, in which case
        stratified KFold will be used.

    shuffle : boolean, optional, default False
        if True will use shuffle = True from StratiedKFold

    random_state : int or None, default = None
        will be passed to the StratifiedKFold object

    Returns
    -------
    checked_cv : a cross-validator instance.
        The return value is a cross-validator which generates the train/test
        splits via the ``split`` method.
    """
    if cv is None:
        cv = 3

    if isinstance(cv, sklearn.model_selection._split.numbers.Integral):
        if (
            classifier
            and (y is not None)
            and (sklearn.model_selection._split.type_of_target(y) in ("binary", "multiclass"))
        ):

            return sklearn.model_selection.StratifiedKFold(cv, shuffle=shuffle, random_state=random_state)

        else:
            return sklearn.model_selection.KFold(cv, shuffle=shuffle, random_state=random_state)

    if not hasattr(cv, "split") or isinstance(cv, str):
        if not isinstance(cv, sklearn.model_selection._split.Iterable) or isinstance(cv, str):
            raise ValueError(
                "Expected cv as an integer, cross-validation "
                "object (from sklearn.model_selection) "
                "or an iterable. Got %s." % cv
            )
        return sklearn.model_selection._split._CVIterableWrapper(cv)

    return cv  # New style cv objects are passed without any modification


def create_scoring(estimator, scoring):
    """ create the scoring object, see sklearn check_scoring function """
    if not isinstance(scoring, (tuple, list)) and not isinstance(scoring, dict):
        scoring = [scoring]

    scorers = OrderedDict()
    ### Handle scoring ###
    if isinstance(scoring, dict):
        # I assume dictionnary with key = name of scoring and value = scoring
        for k, s in scoring.items():
            scorers[k] = sklearn.model_selection._validation.check_scoring(estimator, scoring=s)

    else:

        def find_name(s):
            if s is None:
                return "default_score"

            return str(s)

        for i, s in enumerate(scoring):
            k = find_name(s)
            if k in scorers:
                s = s + ("_%d" % i)
                if k in scorers:
                    raise ValueError("duplicate scorer %s" % s)

            scorers[k] = sklearn.model_selection._validation.check_scoring(estimator, scoring=s)

    return scorers



def _score_with_group(estimator,
           X_test,
           y_test,
           groups_test,
           scorer,
           is_multimetric=False):
    """Compute the score(s) of an estimator on a given test set.

    Will return a single float if is_multimetric is False and a dict of floats,
    if is_multimetric is True
    """
    # Copy of sklearn '_score' but where the 'groups' can be passed to the scorer
    

    if is_multimetric:
        return _multimetric_score_with_group(estimator, X_test, y_test, groups_test, scorer)
    else:
        has_group = groups_test is not None and function_has_named_argument(scorer, "groups")
        # True if :
        # * group is passed to the function
        # * the scorer accepts a 'group' argument

        if y_test is None:
            if has_group:
                score = scorer(estimator, X_test, groups_test)
            else:
                score = scorer(estimator, X_test)
        else:
            if has_group:
                score = scorer(estimator, X_test, y_test, groups_test)
            else:
                score = scorer(estimator, X_test, y_test)

        if hasattr(score, 'item'):
            try:
                # e.g. unwrap memmapped scalars
                score = score.item()
            except ValueError:
                # non-scalar?
                pass

        if not isinstance(score, numbers.Number):
            raise ValueError("scoring must return a number, got %s (%s) "
                             "instead. (scorer=%r)"
                             % (str(score), type(score), scorer))
    return score


def _multimetric_score_with_group(estimator, X_test, y_test, groups_test, scorers):
    """Return a dict of score for multimetric scoring"""
    # Copy of sklearn '_multimetric_score' but where the 'groups' can be passed to the scorer
    scores = {}

    for name, scorer in scorers.items():
        has_group = groups_test is not None and function_has_named_argument(scorer, "groups")
        if y_test is None:
            if has_group:
                score = scorer(estimator, X_test, groups_test)
            else:
                score = scorer(estimator, X_test)
            
                
        else:
            if has_group:
                score = scorer(estimator, X_test, y_test, groups_test)
            else:
                score = scorer(estimator, X_test, y_test)

        if hasattr(score, 'item'):
            try:
                # e.g. unwrap memmapped scalars
                score = score.item()
            except ValueError:
                # non-scalar?
                pass
        scores[name] = score

        if not isinstance(score, numbers.Number):
            raise ValueError("scoring must return a number, got %s (%s) "
                             "instead. (scorer=%s)"
                             % (str(score), type(score), name))
    return scores


def cross_validation(
    estimator,
    X,
    y,
    groups=None,
    scoring=None,
    cv=None,
    verbose=1,
    fit_params=None,
    return_predict=False,
    method=None,
    no_scoring=False,
    stopping_round=None,
    stopping_threshold=None,
    approximate_cv=False,
    **kwargs
):
    """ Does a cross-validation on a model,

    Modification of sklearn cross-validation, The main differences from sklearn function are

    * remove paralelle capabilities
    * allow more than one scoring
    * allow return scores and probas or predictions
    * return score on test and train set for each fold
    * bypass complete cv if score are too low
    * call the 'approx_cross_validation' method in the estimator if it exists (allow specific approximate cv for each estimator)

    Parameters
    ----------
    estimator : estimator object implementing 'fit'
        The object to use to fit the data.

    X : array-like
        The data to fit. Can be, for example a list, or an array at least 2d.

    y : array-like, optional, default: None
        The target variable to try to predict in the case of
        supervised learning.

    groups : array-like, optional, default: None
        The groups to use for the CVs

    scoring : string or list of string for each scores
        Can also be a dictionnary of scorers
        A string (see model evaluation documentation) or
        a scorer callable object / function with signature
        ``scorer(estimator, X, y)``.

    cv : int, cross-validation generator or an iterable, optional
        Determines the cross-validation splitting strategy.
        Possible inputs for cv are:

        - None, to use the default 3-fold cross-validation,
        - integer, to specify the number of folds.
        - An object to be used as a cross-validation generator.
        - An iterable yielding train/test splits.

        For integer/None inputs, if ``y`` is binary or multiclass,
        :class:`StratifiedKFold` used. If the estimator is a classifier
        or if ``y`` is neither binary nor multiclass, :class:`KFold` is used.

        Refer :ref:`User Guide <cross_validation>` for the various
        cross-validation strategies that can be used here.

    fit_parameters : dict or None
        Parameters to pass to the fit method of the estimator.

    verbose : integer, optional
        The verbosity level.

    return_predict: boolean, default:False
        if True will also return the out-of-sample predictions

    method : None or string
        the name of the method to use to return predict ('transform','predict','predict_proba',...). if None will guess based on type of estimator

    no_scoring : boolean, default: False
        if True won't score predictions, cv_result will None in that case

    stopping_round : int or None
        if not None the number of the round on which to start looking if the cv must be stopped (ex: stopping_round = 0, stops after first round)

    stopping_threshold : number of None
        if not None the value bellow which we'll stop the CV

    approximate_cv : boolean, default:False
        if True will try to do an approximate cv by call the method on the estimator (if it exist)

    **kwargs : keywords arguments to be passed to method call

    Returns
    -------
    cv_res : pd.DataFrame (None if 'no_scoring = True')

    outsample prediction (only if return_predict is True)

    """
    if not return_predict and no_scoring:
        raise ValueError("Nothing will be returned")

    ############################
    ### Argument preparation ###
    ############################

    ### make everything indexable ###
    X, y = sklearn.model_selection._validation.indexable(X, y)
    if groups is not None:
        groups, _ = sklearn.model_selection._validation.indexable(groups,None)

    if isinstance(scoring, str):
        scoring = [scoring]

    ### Scoring ###
    if not no_scoring:
        scorers = create_scoring(estimator, scoring)
    # Here : scorers is a dictionnary of scorers objects

    estimator_is_classifier = sklearn.base.is_classifier(estimator)
    estimator_is_regressor = sklearn.base.is_regressor(estimator)

    ### Checks ###
    if not estimator_is_classifier and not estimator_is_regressor:
        # This is a transformer
        if not return_predict:
            raise ValueError("This is a transformer it should only be called with 'return_predict = True'")

        if not no_scoring:
            raise ValueError("This is a transformer it should only be called with 'no_scoring = True'")

    ### Handle cv ###
    cv = create_cv(cv, y, classifier=estimator_is_classifier, shuffle=True, random_state=123)

    ### Handle fit params ###
    if fit_params is None:
        fit_params = {}

    #####################################
    ### Method to use for predictions ###
    #####################################
    if method is None:

        if estimator_is_classifier:
            method = "predict_proba"

        elif estimator_is_regressor:
            method = "predict"

        else:
            method = "transform"

    if hasattr(estimator, "approx_cross_validation") and approximate_cv:

        if verbose:
            print("use approx_cross_validation of estimator (%s)" % str(type(estimator)))

        ##########################################################
        ### estimator can do its own 'approx_cross_validation' ###
        ##########################################################
        result = estimator.approx_cross_validation(
            X=X,
            y=y,
            groups=groups,
            cv=cv,
            scoring=scoring,
            verbose=verbose,
            fit_params=fit_params,
            return_predict=return_predict,
            method=method,
            no_scoring=no_scoring,
            stopping_round=stopping_round,
            stopping_threshold=stopping_threshold,
            **kwargs
        )

        return result

    ###########################################
    ### Check that cv_transform is possible ###
    ###########################################
    if method == "transform" and return_predict:
        if hasattr(estimator, "can_cv_transform"):
            if not estimator.can_cv_transform():
                raise ValueError(
                    "You can't use both method = 'transform' and return_predict for this estimator : %s"
                    % (str(type(estimator)))
                )

    ##########################################################################
    ### estimator doesn't have a special 'approx_cross_val_predict' method ###
    ##########################################################################

    prediction_blocks = []
    all_results = []
    if method in ("predict_proba", "predict_log_proba", "decision_function"):
        classes = np.sort(np.unique(y))

    stop_cv = False
    max_main_scorer = None
    #################
    ### Main Loop ###
    #################
    for i, (train, test) in enumerate(cv.split(X, y, groups=groups)):

        if verbose:
            print("cv %d started\n" % i)

        ### Clone the estimator ###
        cloned_estimator = sklearn.base.clone(estimator)

        ### split train test ###
        X_train, y_train = sklearn.model_selection._validation._safe_split(estimator, X, y, train)
        if groups is not None:
            groups_train, _ = sklearn.model_selection._validation._safe_split(estimator, groups,None, train)
        else:
            groups_train = None
    
        
        X_test, y_test = sklearn.model_selection._validation._safe_split(estimator, X, y, test, train)
        if groups is not None:
            groups_test, _ = sklearn.model_selection._validation._safe_split(estimator, groups,None, test, train)
        else:
            groups_test = None
        

        if hasattr(X_test, "index"):
            index_test = X_test.index
        else:
            index_test = test

        start_fit = time()

        ### Fit estimator ###
        if y_train is None:
            cloned_estimator.fit(X_train, **fit_params)
        else:
            cloned_estimator.fit(X_train, y_train, **fit_params)

        fit_time = time() - start_fit

        if return_predict:
            func = getattr(cloned_estimator, method)
            predictions = func(X_test)

            ## re-alignement with class ##
            if method in ("predict_proba", "predict_log_proba", "decision_function"):

                float_min = np.finfo(predictions.dtype).min
                default_values = {"decision_function": float_min, "predict_log_proba": float_min, "predict_proba": 0}

                predictions_for_all_classes = pd.DataFrame(default_values[method], index=index_test, columns=classes)
                for j, c in enumerate(cloned_estimator.classes_):
                    predictions_for_all_classes[c] = predictions[:, j]

                predictions = predictions_for_all_classes

            prediction_blocks.append((predictions, test))

        result = OrderedDict()

        ### Score test ###
        if not no_scoring:
            start_score = time()
            test_scores_dictionary = _score_with_group(
                cloned_estimator, X_test, y_test, groups_test, scorer=scorers, is_multimetric=True
            )
            # Here : scorers is a dictionary of scorers, hence is_multimetric = True
            score_time = time() - start_score

            ### Score train ###
            train_scores_dictionary = _score_with_group(
                cloned_estimator, X_train, y_train, groups_train, scorer=scorers, is_multimetric=True
            )

            ### Put everything into a dictionnary ###
            for k, v in test_scores_dictionary.items():
                result["test_%s" % k] = v

            for k, v in train_scores_dictionary.items():
                result["train_%s" % k] = v

        result["fit_time"] = fit_time

        if not no_scoring:
            result["score_time"] = score_time

        result["n_test_samples"] = sklearn.model_selection._validation._num_samples(X_test)
        result["fold_nb"] = i

        all_results.append(result)

        ### Look if I need to stop ###
        if not no_scoring:
            stop_cv = False
            if stopping_round is not None and i >= stopping_round and stopping_threshold is not None:

                if isinstance(scoring, list) and scoring[0] in test_scores_dictionary:
                    main_score_name = scoring[0]
                else:
                    main_score_name = sorted(test_scores_dictionary.keys())[0]

                if max_main_scorer is None:
                    max_main_scorer = test_scores_dictionary[main_score_name]
                else:
                    max_main_scorer = max(max_main_scorer, test_scores_dictionary[main_score_name])

                if max_main_scorer <= stopping_threshold:
                    # I stop if ALL the scorers are bad
                    stop_cv = True

            if stop_cv:
                break

    ### Merge everything together ###

    # Concatenate the predictions
    if return_predict:
        if stop_cv:
            predictions = None

            if verbose:
                print("I can't return predictions since I stopped the CV")

        else:
            predictions = [pred_block_i for pred_block_i, _ in prediction_blocks]
            test_indices = np.concatenate([indices_i for _, indices_i in prediction_blocks])

            if not sklearn.model_selection._validation._check_is_permutation(
                test_indices, sklearn.model_selection._validation._num_samples(X)
            ):

                if verbose:
                    print("I can't return predictions as this CV isn't a partition only works for partitions")

                predictions = None

            else:
                inv_test_indices = np.empty(len(test_indices), dtype=int)
                inv_test_indices[test_indices] = np.arange(len(test_indices))

                # Check for sparse predictions
                if sp.issparse(predictions[0]):
                    predictions = sp.vstack(predictions, format=predictions[0].format)
                    predictions = predictions[inv_test_indices]

                elif hasattr(predictions[0], "iloc"):
                    predictions = pd.concat(predictions, axis=0)
                    predictions = predictions.iloc[inv_test_indices, :]

                else:
                    predictions = np.concatenate(predictions)
                    predictions = predictions[inv_test_indices]

    ### Result ###
    if not no_scoring:
        cv_res = pd.DataFrame(all_results)
    else:
        cv_res = None

    if return_predict:
        return cv_res, predictions
    else:
        return cv_res


########################################
#### score prediction for clustering ###
########################################
def score_from_params_clustering(
    estimator,
    X,
    scoring=None,
    verbose=1,
    fit_params=None,
    return_predict=False,
    method=None,
    no_scoring=False,
    **kwargs
):

    """ scores a clustering model

    Parameters
    ----------
    estimator : estimator object implementing 'fit'
        The clusterer object to use to fit the data.

    X : array-like
        The data to fit. Can be, for example a list, or an array at least 2d.

    scoring : string or list of string for each scores
        Can also be a dictionnary of scorers
        A string (see model evaluation documentation) or
        a scorer callable object / function with signature
        ``scorer(estimator, X, y)``.

    fit_params : dict or None
        Parameters to pass to the fit method of the estimator.

    verbose : integer, optional
        The verbosity level.

    return_predict: boolean, default:False
        if True will return the predictions

    method : None or string
        the name of the method to use to return predict ('transform','predict'). if None will guess based on type of estimator

    no_scoring : boolean, default: False
        if True won't score predictions, result will None in that case

    **kwargs : keywords arguments to be passed to method call

    Returns
    -------
    cv_res : pd.DataFrame (None if 'no_scoring = True')

    prediction (only if return_predict is True)

    """

    if not return_predict and no_scoring:
        raise ValueError("Nothing will be returned")

    estimator_is_clusterer = is_clusterer(estimator)
    ### Checks ###
    if not estimator_is_clusterer:
        # This is a transformer
        if not return_predict:
            raise ValueError("This is a transformer it should only be called with 'return_predict = True'")

        if not no_scoring:
            raise ValueError("This is a transformer it should only be called with 'no_scoring = True'")

    ############################
    ### Argument preparation ###
    ############################
    if isinstance(scoring, str):
        scoring = [scoring]

    ### Scoring ###
    if not no_scoring:
        scorers = create_scoring(estimator, scoring)
    # Here : scorers is a dictionnary of scorers objects

    ### Handle fit params ###
    if fit_params is None:
        fit_params = {}

    #####################################
    ### Method to use for predictions ###
    #####################################
    ### TODO: method depends on the scoring function
    if method is None:
        method = "fit_predict"
        # method = "transform"

    ### Clone the estimator ###
    cloned_estimator = sklearn.base.clone(estimator)

    start_fit = time()

    ### Fit estimator ###
    pred = cloned_estimator.fit_predict(X, **fit_params)

    fit_time = time() - start_fit

    if return_predict:
        predictions = pred

    ### Score ###
    if not no_scoring:
        start_score = time()
        scores_dictionnary = sklearn.model_selection._validation._score(
            cloned_estimator, X, None, scorer=scorers, is_multimetric=True
        )
        # Here : scorers is a dicttionnary of scorers, hence is_multimetric = True
        score_time = time() - start_score

    ### Put everything into a dictionnary ###
    result = OrderedDict()
    if not no_scoring:
        for k, v in scores_dictionnary.items():
            result["test_%s" % k] = v

    result["fit_time"] = fit_time

    if not no_scoring:
        result["score_time"] = score_time

    ### Result ###
    if not no_scoring:
        res = pd.DataFrame([result])
    else:
        res = None

    if return_predict:
        return res, predictions
    else:
        return res
