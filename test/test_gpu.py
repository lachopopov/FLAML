import pickle
import shutil
import sys

import pytest


def test_xgboost():
    import numpy as np
    import scipy.sparse
    from sklearn.datasets import make_moons
    from xgboost.core import XGBoostError

    from flaml import AutoML

    try:
        X_train = scipy.sparse.eye(900000)
        y_train = np.random.randint(2, size=900000)
        automl = AutoML()
        automl.fit(
            X_train,
            y_train,
            estimator_list=["xgb_limitdepth", "xgboost"],
            time_budget=5,
            gpu_per_trial=1,
        )

        train, label = make_moons(n_samples=300000, shuffle=True, noise=0.3, random_state=None)
        automl = AutoML()
        automl.fit(
            train,
            label,
            estimator_list=["xgb_limitdepth", "xgboost"],
            time_budget=5,
            gpu_per_trial=1,
        )
        automl.fit(
            train,
            label,
            estimator_list=["xgb_limitdepth", "xgboost"],
            time_budget=5,
        )
    except XGBoostError:
        # No visible GPU is found for XGBoost.
        return


@pytest.mark.skipif(sys.platform == "darwin", reason="do not run on mac os")
def _test_hf_data():
    import requests
    from datasets import load_dataset

    from flaml import AutoML

    try:
        train_dataset = load_dataset("glue", "mrpc", split="train[:1%]").to_pandas()
        dev_dataset = load_dataset("glue", "mrpc", split="validation[:1%]").to_pandas()
        test_dataset = load_dataset("glue", "mrpc", split="test[:1%]").to_pandas()
    except requests.exceptions.ConnectionError:
        return

    # Tests will only run if there is a GPU available
    try:
        import ray

        pg = ray.util.placement_group([{"CPU": 1, "GPU": 1}])

        if not pg.wait(timeout_seconds=10):  # Wait 10 seconds for resources
            raise RuntimeError("No available node types can fulfill resource request!")
    except RuntimeError:
        return

    custom_sent_keys = ["sentence1", "sentence2"]
    label_key = "label"

    X_train = train_dataset[custom_sent_keys]
    y_train = train_dataset[label_key]

    X_val = dev_dataset[custom_sent_keys]
    y_val = dev_dataset[label_key]

    X_test = test_dataset[custom_sent_keys]

    automl = AutoML()

    automl_settings = {
        "gpu_per_trial": 1,
        "max_iter": 2,
        "time_budget": 5000,
        "task": "seq-classification",
        "metric": "accuracy",
        "log_file_name": "seqclass.log",
        "use_ray": True,
    }

    automl_settings["fit_kwargs_by_estimator"] = {
        "transformer": {
            "model_path": "facebook/muppet-roberta-base",
            "output_dir": "test/data/output/",
            "fp16": True,
        }
    }

    automl.fit(X_train=X_train, y_train=y_train, X_val=X_val, y_val=y_val, **automl_settings)

    automl = AutoML()
    automl.retrain_from_log(X_train=X_train, y_train=y_train, train_full=True, record_id=0, **automl_settings)
    with open("automl.pkl", "wb") as f:
        pickle.dump(automl, f, pickle.HIGHEST_PROTOCOL)
    with open("automl.pkl", "rb") as f:
        automl = pickle.load(f)
    shutil.rmtree("test/data/output/")
    automl.predict(X_test)
    automl.predict(["test test", "test test"])
    automl.predict(
        [
            ["test test", "test test"],
            ["test test", "test test"],
            ["test test", "test test"],
        ]
    )

    automl.predict_proba(X_test)
    print(automl.classes_)


if __name__ == "__main__":
    _test_hf_data()
