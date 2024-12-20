# PNPP (plant NeRF preprocessing)

目的归一化处理各种设备，各种方法采集的数据，供给给PSN、TDNeRF等使用



## 依赖安装

### 1. ffmpeg

### 2. colmap

```
需要添加到系统环境变量，即在命令行输入colmap能找到路径
```

### 3. pip

```
pip install iopenpyxl
pip install tkinterdnd2
pip install opencv-python
```

### 4. pnpp

```
cd PNPP
pip install -e .
```

-----------------------------------------------------------------------------------------------------------------------

2024年10月23日 Timothy，Abyss

## 一、环绕采集的RGB视频

## （handheld camera surrounding acquisition_HCSA）

#### 1. 以视频建立文件夹

##### (窗口化)

可以根据弹出的窗口选择一对一或者多个视频合并为一个处理单位

```
python  -m pnpp.hcsa.CFfV.create_folder_from_videos
```

##### (命令行)	

在命令行中执行以下命令以进行 1 对 1 模式：

```
python -m pnpp.hcsa.CFfV.CFfV_cli --inputpath "D:\abyss\Data\Test2"
```

在命令行中执行以下命令以进行多视频合并模式，使用自定义分隔符（如 `-`）：

```
python -m pnpp.hcsa.CFfV.CFfV_cli --inputpath "D:\abyss\Data\Test2" --separator "-"
```

#### * 2. 批量重命名文件

```
python -m pnpp.hcsa.Rename.Rename_file_and_dir --inputdir "D:\abyss\Data\Test2" --rename 804_Eggplant  --dirname 114_Eggplant  --start_num 12
```

#### 3. 视频抽帧处理

---已选择了图片质量好且内存占用合理的参数，可以在`Get_Frame`中自行调节

##### 单个目标处理（少数情况）

##### (命令行)

```
python-m pnpp.hcsa.Get_Frame.Get_Frame --inputpath "D:\abyss\Data\C\1" --fps 1
```

##### 整个文件批处理

##### (窗口化)

```
python -m pnpp.hcsa.Get_Frame.DF_dir
```

##### (命令行)

```
python -m pnpp.hcsa.Get_Frame.DF_dir --inputpath "D:\abyss\Data\Test" --fps 3
```

#### 4. 推测相机位姿

##### 单个目标处理（少数情况）

##### pycharm

```
pnpp\hcsa\SfM\Do_SfM.py
```

##### 命令行

```
使用instantngp的colmap2nerf即可
```

##### 整个文件批处理

```
python -m pnpp.hcsa.SfM.Do_SfM_dir
```

----------------------------------------

2024年10月24日 Timothy，Abyss

#### Tools

批量复制transforms.json文件到skip文件夹

```
python -m pnpp.hcsa.SfM.Do_copy_transforms_dir
```

批量移动transforms.json文件到skip文件夹

```
python -m pnpp.hcsa.SfM.delete_transforms
```

批量移动transforms.json文件到skip文件夹（只删除Size较小的）

```
python -m pnpp.hcsa.SfM.Do_delete_byszie_dir
```

批量将transforms.json放置回各个文件夹

```
python -m pnpp.hcsa.SfM.Do_restore_trans_dir
```









## 二、机械臂等拍摄的多视角图像

## （Robotic arm automatic acquisition_RAAA）

```

```

#### 1. 批量重命名文件夹

#### 2. 推测相机位姿



## 三、深度相机采集的RGB-D视频

## （handheld RGB-D forward acquisition_HDFA）

采集到的初始数据是多个mkv文件。

### *单个视频即为一个单位

```

```

#### 1. 数据格式转化

#### 2. Tiff等格式数据构造

