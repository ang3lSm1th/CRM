import os
from pathlib import Path

import MySQLdb
import joblib
from dotenv import load_dotenv
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.model_selection import train_test_split

load_dotenv(override=True)


def get_connection():
    return MySQLdb.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        user=os.getenv("MYSQL_USER", "root"),
        passwd=os.getenv("MYSQL_PASSWORD", "123456"),
        db=os.getenv("MYSQL_DB", "u349183440_crm_orbes"),
        port=int(os.getenv("MYSQL_PORT", "3307")),
        charset="utf8mb4",
    )


def table_exists(cur, table_name):
    cur.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s
        """,
        (table_name,),
    )
    return int(cur.fetchone()[0] or 0) > 0


def load_training_data(cur):
    sql = """
        SELECT
            l.id AS lead_id,
            DATEDIFF(CURDATE(), l.fecha) AS dias_desde_alta,
            CASE WHEN l.cliente_id IS NULL THEN 0 ELSE 1 END AS tiene_cliente,
            COALESCE(s.total_seguimientos, 0) AS total_seguimientos,
            COALESCE(s.dias_desde_ultimo_seguimiento, 999) AS dias_desde_ultimo_seguimiento,
            COALESCE(s.monto_promedio, 0) AS monto_promedio_seguimiento,
            CASE WHEN v.lead_id IS NULL THEN 0 ELSE 1 END AS compro
        FROM leads l
        LEFT JOIN (
            SELECT
                lead_id,
                COUNT(*) AS total_seguimientos,
                DATEDIFF(CURDATE(), MAX(fecha_guardado)) AS dias_desde_ultimo_seguimiento,
                AVG(COALESCE(monto, 0)) AS monto_promedio
            FROM seguimientos
            GROUP BY lead_id
        ) s ON s.lead_id = l.id
        LEFT JOIN (
            SELECT DISTINCT lead_id
            FROM ventas_concretadas
            WHERE lead_id IS NOT NULL
        ) v ON v.lead_id = l.id
    """
    cur.execute(sql)
    rows = cur.fetchall()

    X, y = [], []
    for row in rows:
        X.append(
            [
                float(row[1] or 0),
                float(row[2] or 0),
                float(row[3] or 0),
                float(row[4] or 999),
                float(row[5] or 0),
            ]
        )
        y.append(int(row[6] or 0))
    return X, y


def save_metric(cur, model_name, version, metric, value, obs=None):
    if not table_exists(cur, "metricas_modelos"):
        return

    cur.execute(
        """
        INSERT INTO metricas_modelos
        (modelo_nombre, modelo_version, metrica_nombre, metrica_valor, observacion, created_at)
        VALUES (%s, %s, %s, %s, %s, NOW())
        """,
        (model_name, version, metric, float(value), obs),
    )


def main():
    conn = get_connection()
    cur = conn.cursor()

    try:
        required = ["leads", "seguimientos", "ventas_concretadas"]
        missing = [t for t in required if not table_exists(cur, t)]
        if missing:
            print(f"Faltan tablas para entrenar: {', '.join(missing)}")
            return

        X, y = load_training_data(cur)
        if len(X) < 40:
            print("Datos insuficientes para entrenar (mínimo recomendado: 40 leads).")
            return

        if len(set(y)) < 2:
            print("No hay clases suficientes en el label (compro=0/1).")
            return

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.25, random_state=42, stratify=y
        )

        model = RandomForestClassifier(
            n_estimators=220,
            max_depth=10,
            min_samples_leaf=2,
            random_state=42,
            class_weight="balanced",
        )
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)

        acc = accuracy_score(y_test, y_pred)
        prec = precision_score(y_test, y_pred, zero_division=0)
        rec = recall_score(y_test, y_pred, zero_division=0)
        f1 = f1_score(y_test, y_pred, zero_division=0)

        out_dir = Path("models/ml_models")
        out_dir.mkdir(parents=True, exist_ok=True)
        model_path = out_dir / "compra_model.pkl"
        joblib.dump(model, model_path)

        version = os.getenv("COMPRA_MODEL_VERSION", "rf_v1")
        save_metric(cur, "compra_model", version, "accuracy", acc)
        save_metric(cur, "compra_model", version, "precision", prec)
        save_metric(cur, "compra_model", version, "recall", rec)
        save_metric(cur, "compra_model", version, "f1", f1)
        conn.commit()

        print(f"Modelo guardado en: {model_path}")
        print(
            "Metricas -> "
            f"accuracy={acc:.4f}, precision={prec:.4f}, recall={rec:.4f}, f1={f1:.4f}"
        )
        print(
            "Ejecucion recomendada: una vez por semana o tras cambios grandes de datos."
        )
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
