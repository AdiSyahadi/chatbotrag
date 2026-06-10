from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from app.modules.logger import chat_logger

router = APIRouter()

@router.get("/logs")
def get_logs_ui():
    html = """
    <html>
    <head>
        <title>ChatBot WA Logs</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; padding: 20px; background: #f4f4f9; color: #333; }
            .container { max-width: 1000px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            h2 { color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }
            table { width: 100%; border-collapse: collapse; margin-top: 20px; }
            th, td { padding: 12px; border: 1px solid #ddd; text-align: left; }
            th { background: #34495e; color: white; position: sticky; top: 0; }
            tr:nth-child(even) { background: #f9f9f9; }
            tr:hover { background: #f1f1f1; }
            .INCOMING { color: #27ae60; font-weight: bold; }
            .OUTGOING { color: #2980b9; font-weight: bold; }
            .ERROR { color: #e74c3c; font-weight: bold; }
            .meta-info { font-size: 0.85em; color: #7f8c8d; margin-bottom: 15px; }
        </style>
        <script>
            // Refresh automatically every 5 seconds
            setTimeout(() => { location.reload(); }, 5000);
        </script>
    </head>
    <body>
        <div class="container">
            <h2>📱 Live WhatsApp ChatBot Logs</h2>
            <div class="meta-info">Halaman ini otomatis me-refresh setiap 5 detik.</div>
            <table>
                <tr>
                    <th>Waktu</th>
                    <th>Arah</th>
                    <th>Nomor HP / Kontak</th>
                    <th>Pesan</th>
                    <th>Status</th>
                </tr>
    """
    
    for log in reversed(chat_logger.logs):
        direction_class = "ERROR" if "Error" in log["status"] or "Failed" in log["status"] else log["direction"]
        html += f"""
                <tr>
                    <td>{log['time']}</td>
                    <td class="{direction_class}">{log['direction']}</td>
                    <td>{log['recipient']}</td>
                    <td>{log['content']}</td>
                    <td class="{'ERROR' if 'Error' in log['status'] or 'Failed' in log['status'] else ''}">{log['status']}</td>
                </tr>
        """
        
    html += """
            </table>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html)
