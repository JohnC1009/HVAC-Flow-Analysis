"""
HVAC Calculators Web Application

A Flask-based web application providing 5 HVAC engineering calculators:
1. Conduit Fill (NEC)
2. Pipe Sizing (ASHRAE)
3. Duct Pressure Drop (SMACNA)
4. Fan Laws (AMCA)
5. Pump Laws (Hydraulic Institute)
"""

from flask import Flask, render_template, request, jsonify
from hvac_calculators import (
    calculate_conduit_fill,
    calculate_pipe_sizing,
    calculate_duct_pressure_drop,
    calculate_fan_laws,
    calculate_pump_laws,
    ValidationError,
    HvacCalculatorError,
)

app = Flask(__name__)


@app.route("/")
def index():
    """Render the main calculator page."""
    return render_template("index.html")


@app.route("/api/calculate/conduit", methods=["POST"])
def api_conduit():
    """Calculate conduit fill."""
    try:
        data = request.get_json()
        result = calculate_conduit_fill(
            conduit_type=data.get("conduit_type", "EMT"),
            conduit_size=float(data.get("conduit_size", 1.0)),
            wire_gauge=int(data.get("wire_gauge", 12)),
            num_wires=int(data.get("num_wires", 3)),
            insulation_type=data.get("insulation_type", "THHN"),
        )
        return jsonify({"success": True, "data": result})
    except ValidationError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"success": False, "error": f"Calculation error: {str(e)}"}), 500


@app.route("/api/calculate/pipe", methods=["POST"])
def api_pipe():
    """Calculate pipe sizing."""
    try:
        data = request.get_json()
        result = calculate_pipe_sizing(
            flow_rate_gpm=float(data.get("flow_rate_gpm", 50.0)),
            pipe_material=data.get("pipe_material", "CU"),
            max_velocity_fps=float(data.get("max_velocity_fps", 8.0)),
            max_pressure_drop=float(data.get("max_pressure_drop", 4.0)),
        )
        return jsonify({"success": True, "data": result})
    except ValidationError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"success": False, "error": f"Calculation error: {str(e)}"}), 500


@app.route("/api/calculate/duct", methods=["POST"])
def api_duct():
    """Calculate duct pressure drop."""
    try:
        data = request.get_json()
        result = calculate_duct_pressure_drop(
            airflow_cfm=float(data.get("airflow_cfm", 1000)),
            duct_width_in=float(data.get("duct_width_in", 12)),
            duct_height_in=float(data.get("duct_height_in", 12)),
            duct_material=data.get("duct_material", "galvanized"),
            length_ft=float(data.get("length_ft", 100)),
        )
        return jsonify({"success": True, "data": result})
    except ValidationError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"success": False, "error": f"Calculation error: {str(e)}"}), 500


@app.route("/api/calculate/fan", methods=["POST"])
def api_fan():
    """Calculate fan laws."""
    try:
        data = request.get_json()
        calc_type = data.get("calculation_type", "cfm")
        
        params = {
            "cfm_1": float(data.get("cfm_1", 10000)),
            "rpm_1": float(data.get("rpm_1", 1200)),
            "bhp_1": float(data.get("bhp_1", 10.0)),
            "calculation_type": calc_type,
        }
        
        if calc_type == "cfm":
            params["cfm_2"] = float(data.get("cfm_2", 12000))
        else:
            params["rpm_2"] = float(data.get("rpm_2", 1500))
        
        result = calculate_fan_laws(**params)
        return jsonify({"success": True, "data": result})
    except ValidationError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"success": False, "error": f"Calculation error: {str(e)}"}), 500


@app.route("/api/calculate/pump", methods=["POST"])
def api_pump():
    """Calculate pump laws."""
    try:
        data = request.get_json()
        calc_type = data.get("calculation_type", "gpm")
        
        params = {
            "gpm_1": float(data.get("gpm_1", 500)),
            "rpm_1": float(data.get("rpm_1", 1750)),
            "head_1": float(data.get("head_1", 100)),
            "bhp_1": float(data.get("bhp_1", 25.0)),
            "calculation_type": calc_type,
        }
        
        if calc_type == "gpm":
            params["gpm_2"] = float(data.get("gpm_2", 600))
        else:
            params["rpm_2"] = float(data.get("rpm_2", 2100))
        
        result = calculate_pump_laws(**params)
        return jsonify({"success": True, "data": result})
    except ValidationError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"success": False, "error": f"Calculation error: {str(e)}"}), 500


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
