# Setup instructions for MyAGV (Jetson Nano)

1. **Transfer Files**: Copy the entire `deploy_agv` folder to your MyAGV.
   ```bash
   scp -r deploy_agv ubuntu@192.168.x.x:~/
   ```

2. **Install Dependencies**:
   SSH into the robot and run:
   ```bash
   cd ~/deploy_agv
   pip3 install -r requirements.txt
   ```
   *Note: `opencv-python` might already be installed on the Jetson. If you have issues, remove it from requirements.txt.*

3. **Find your PC's IP**:
   Run `ipconfig` (Windows) or `ifconfig` (Linux/Mac) on your computer to find your local IP address (e.g., 192.168.2.100).

4. **Run the Client**:
   Replace the IP with your backend's IP.
   ```bash
   python3 agv_client.py --url ws://YOUR_PC_IP:8000/ws
   ```
   
   If using a specific camera (not default 0):
   ```bash
   python3 agv_client.py --url ws://YOUR_PC_IP:8000/ws --camera 0
   ```
