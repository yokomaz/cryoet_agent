---
name: Motion Correction
description: Perform motion correction for frames data of Cryo-EM, Cryo-ET data. This skill is used when the agent plans a motion correction step in the cryo-ET data processing workflow.
---

# Motion Correction
Motion correction is the process of algorithmically correcting for motion of the electron microscope stage and the sample ice itself to recover image quality lost by motion blurring.

Cryo-EM and Cryo-ET data is collected in the form of movies, which are each a series of individual frames. Since a frame is usually between 0.1 and 0.2 seconds, the detector does not accumulate enough electron dose for clear identification of the target. However, the brief length of time significantly reduces the amount of in-frame motion blur.

## Input data 
The input data for motion correction typically consists of **raw movie frames** collected from the electron microscope. These frames can be in various formats such as TIFF, MRC, or EER. Additionally, a gain reference file may be required for accurate correction.

## Tools could be used for Motion Correction
1. Warp: Warp is a software package for real-time processing of cryo-EM data, including motion correction operations. The detailed usage for Warp in motion correction can be found in the ./reference/warp_motion_correction.md file.
2. MotionCor series: MotionCor is a widely used software for motion correction in cryo-EM data processing. The detailed usage for MotionCor in motion correction can be found in the ./reference/motioncor_motion_correction.md file.
