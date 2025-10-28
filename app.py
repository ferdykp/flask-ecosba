# import os
# import json
# import math
# import pulp
# import numpy as np
# import matplotlib
# matplotlib.use('Agg')  # <--- tambahkan baris ini
# import matplotlib.pyplot as plt
# from datetime import datetime
# from flask import Flask, render_template, request, url_for, redirect

import os 
import json 
import math 
import pulp 
import numpy as np 
import matplotlib.pyplot as plt 
from datetime import datetime 
from flask import Flask, render_template, request, url_for, redirect

app = Flask(__name__)
UPLOAD_FOLDER = 'static/hasil_gambar'
HISTORY_FILE = 'data/history.json'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)


def ilp_sensor_placement(luas_lahan, panjang_lahan, lebar_lahan, resolusi=2.5):
    nx = int(math.ceil(panjang_lahan / resolusi))
    ny = int(math.ceil(lebar_lahan / resolusi))
    positions = [(i, j) for i in range(nx) for j in range(ny)]
    pos_coords = {(i, j): (i * resolusi + resolusi / 2, j * resolusi + resolusi / 2) for (i, j) in positions}
    luas_sensor = 154
    radius = math.sqrt(luas_sensor / math.pi)

    model = pulp.LpProblem("Penempatan_Sensor_ILP", pulp.LpMinimize)
    sensor_vars = pulp.LpVariable.dicts("Sensor", positions, 0, 1, pulp.LpBinary)

    model += pulp.lpSum(sensor_vars[pos] for pos in positions)

    for (i, j) in positions:
        xi, yi = pos_coords[(i, j)]
        covered_by = []
        for (si, sj) in positions:
            xs, ys = pos_coords[(si, sj)]
            if (xi - xs) ** 2 + (yi - ys) ** 2 <= radius ** 2:
                covered_by.append(sensor_vars[(si, sj)])
        model += pulp.lpSum(covered_by) >= 1

    model.solve()
    sensor_terpasang = [pos_coords[pos] for pos in positions if pulp.value(sensor_vars[pos]) == 1]
    return panjang_lahan, lebar_lahan, sensor_terpasang, radius


def hitung_area_tidak_tercakup(sensor_coords, radius, panjang, lebar, grid_res=0.5):
    x_points = np.arange(0, panjang, grid_res)
    y_points = np.arange(0, lebar, grid_res)
    total_points = 0
    uncovered_points = 0

    for x in x_points:
        for y in y_points:
            total_points += 1
            tercakup = any(math.hypot(x - sx, y - sy) <= radius for sx, sy in sensor_coords)
            if not tercakup:
                uncovered_points += 1

    return (uncovered_points / total_points) * 100


def simpan_riwayat(data):
    try:
        with open(HISTORY_FILE, 'r') as f:
            riwayat = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        riwayat = []

    riwayat.insert(0, data)
    with open(HISTORY_FILE, 'w') as f:
        json.dump(riwayat, f, indent=2)

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/simulation', methods=['GET', 'POST'])
def simulation():
    if request.method == 'POST':
        nama = request.form['nama_daerah']
        luas = float(request.form['luas_lahan'])

        shapes = {
            "Persegi": (math.sqrt(luas), math.sqrt(luas)),
            "Panjang > Lebar (2:1)": (math.sqrt(2 * luas), math.sqrt(2 * luas) / 2),
            "Lebar > Panjang (1:2)": (math.sqrt(luas / 2), math.sqrt(luas / 2) * 2),
        }

        fig, axs = plt.subplots(1, 3, figsize=(18, 6))
        hasil = []

        for idx, (label, (p, l)) in enumerate(shapes.items()):
            panjang, lebar, sensors, radius = ilp_sensor_placement(luas, p, l)
            persen_tidak_tercakup = hitung_area_tidak_tercakup(sensors, radius, panjang, lebar)

            ax = axs[idx]
            ax.set_xlim(0, panjang)
            ax.set_ylim(0, lebar)
            ax.set_aspect('equal')
            ax.grid(True)

            for i, (x, y) in enumerate(sensors):
                circle = plt.Circle((x, y), radius, color='green', alpha=0.3)
                ax.add_patch(circle)
                ax.plot(x, y, 'ro')
                ax.text(x, y, f"NS{i+1}", color='darkred', fontsize=8, ha='center')

            ax.plot(panjang / 2, lebar / 2, 'bo')
            ax.text(panjang / 2, lebar / 2, 'Main Unit', color='blue', fontsize=10, ha='center', va='center')
            ax.set_title(f"{label} ({int(luas)} m²)")
            ax.set_xlabel("Panjang (m)")
            ax.set_ylabel("Lebar (m)")

            hasil.append({
                "label": label,
                "sensor": [(round(x, 2), round(y, 2)) for (x, y) in sensors],
                "tidak_tercakup": round(persen_tidak_tercakup, 2)
            })

        filename = f"simulasi_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        #gambar_path = os.path.join(UPLOAD_FOLDER, filename)
        gambar_path = os.path.join(UPLOAD_FOLDER, filename).replace('\\', '/')
        plt.tight_layout()
        plt.savefig(gambar_path)
        plt.close()

        simpan_riwayat({
            "nama_daerah": nama,
            "luas_lahan": luas,
            "tanggal": datetime.now().strftime('%Y-%m-%d %H:%M'),
            "hasil": hasil,
            "gambar": gambar_path
        })

        return render_template('simulation.html', gambar=gambar_path, hasil=hasil, nama_daerah=nama, luas_lahan=luas)

    return render_template('simulation.html')


@app.route('/history')
def history():
    try:
        with open(HISTORY_FILE, 'r') as f:
            data = json.load(f)
    except:
        data = []
    return render_template('history.html', data=data)

@app.route('/delete/<int:index>', methods=['POST'])
def delete(index):
    try:
        with open(HISTORY_FILE, 'r') as f:
            history_list = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        history_list = []

    if 0 <= index < len(history_list):
        try:
            # Hapus file gambar jika masih ada
            gambar_path = history_list[index]['gambar']
            if os.path.exists(gambar_path):
                os.remove(gambar_path)
        except:
            pass

        # Hapus data dari list
        history_list.pop(index)

        # Tulis ulang ke file
        with open(HISTORY_FILE, 'w') as f:
            json.dump(history_list, f, indent=2)

    return redirect(url_for('history'))



if __name__ == '__main__':
    app.run(debug=True)
