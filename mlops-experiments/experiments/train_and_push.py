import os
import shutil
import mlflow
import mlflow.sklearn
from sklearn.datasets import load_iris
from sklearn.linear_model import SGDClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
from prometheus_client import CollectorRegistry, Gauge, push_to_gateway

# ── Configuration ──────────────────────────────────────────────────────────────
MLFLOW_URI      = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
PUSHGATEWAY_URL = os.getenv("PUSHGATEWAY_URL",    "localhost:9091")
BEST_MODEL_DIR  = "best_model"

mlflow.set_tracking_uri(MLFLOW_URI)
mlflow.set_experiment("iris-experiment")

# ── Dataset ────────────────────────────────────────────────────────────────────
iris = load_iris()
X_train, X_test, y_train, y_test = train_test_split(
    iris.data, iris.target, test_size=0.2, random_state=42
)

# ── Hyperparameter grid ────────────────────────────────────────────────────────
param_grid = [
    {"learning_rate": 0.01, "epochs": 50},
    {"learning_rate": 0.05, "epochs": 100},
    {"learning_rate": 0.1,  "epochs": 150},
]

best_accuracy = 0.0
best_run_id   = None

# ── Training loop ──────────────────────────────────────────────────────────────
for params in param_grid:
    lr     = params["learning_rate"]
    epochs = params["epochs"]

    with mlflow.start_run() as run:
        run_id = run.info.run_id
        print(f"\n▶ Run {run_id}  lr={lr}  epochs={epochs}")

        model = SGDClassifier(
            loss="hinge",
            eta0=lr,
            learning_rate="constant",
            max_iter=epochs,
            random_state=42
        )
        model.fit(X_train, y_train)

        preds    = model.predict(X_test)
        accuracy = accuracy_score(y_test, preds)
        loss     = 1.0 - accuracy          # proxy loss

        # ── Log to MLflow ──────────────────────────────────────────────────────
        mlflow.log_params({"learning_rate": lr, "epochs": epochs})
        mlflow.log_metrics({"accuracy": accuracy, "loss": loss})
        mlflow.sklearn.log_model(model, artifact_path="model")

        print(f"   accuracy={accuracy:.4f}  loss={loss:.4f}")

        # ── Push to PushGateway ───────────────────────────────────────────────
        registry = CollectorRegistry()
        g_acc  = Gauge("mlflow_accuracy", "MLflow run accuracy",
                       ["run_id"], registry=registry)
        g_loss = Gauge("mlflow_loss",     "MLflow run loss",
                       ["run_id"], registry=registry)
        g_acc.labels(run_id=run_id).set(accuracy)
        g_loss.labels(run_id=run_id).set(loss)

        push_to_gateway(PUSHGATEWAY_URL, job="mlflow_training",
                        grouping_key={"run_id": run_id},
                        registry=registry)
        print(f"   ✔ Metrics pushed to PushGateway")

        # ── Track best ────────────────────────────────────────────────────────
        if accuracy > best_accuracy:
            best_accuracy = accuracy
            best_run_id   = run_id

# ── Copy best model locally ────────────────────────────────────────────────────
if best_run_id:
    print(f"\n★ Best run: {best_run_id}  accuracy={best_accuracy:.4f}")
    artifact_uri = mlflow.get_run(best_run_id).info.artifact_uri
    local_path   = mlflow.artifacts.download_artifacts(
        run_id=best_run_id, artifact_path="model"
    )
    if os.path.exists(BEST_MODEL_DIR):
        shutil.rmtree(BEST_MODEL_DIR)
    shutil.copytree(local_path, BEST_MODEL_DIR)
    print(f"★ Best model saved to ./{BEST_MODEL_DIR}/")