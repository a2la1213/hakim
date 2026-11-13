"""DeepFilterNet 3 sur un son brut (f32, entrelacé) : lancé par studio_pro.debruiter_dfn dans son venv à part
(JARVIS_PYTHON_DEBRUITAGE : python 3.11, deepfilternet 0.5.6, torch 2.0.1, torchaudio 2.0.2, numpy < 2).
usage : studio_pro_dfn.py entree.f32 sortie.f32 sr canaux atténuation_max_db"""
import sys

import numpy as np


def main():
    entree, sortie, sr, ch, att = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), float(sys.argv[5])
    import torch
    import torchaudio.functional as AF
    from df.enhance import enhance, init_df
    x = np.fromfile(entree, np.float32).reshape(-1, ch).T.copy()
    modele, etat, _ = init_df(log_level="ERROR")
    t = torch.from_numpy(x)
    sr_df = etat.sr()
    if sr != sr_df:
        t = AF.resample(t, sr, sr_df)
    y = enhance(modele, etat, t, atten_lim_db=att)
    if sr != sr_df:
        y = AF.resample(y, sr_df, sr)
    y = y.numpy()[:, : x.shape[1]]
    if y.shape[1] < x.shape[1]:
        y = np.pad(y, ((0, 0), (0, x.shape[1] - y.shape[1])))
    np.ascontiguousarray(y.T, np.float32).tofile(sortie)


if __name__ == "__main__":
    main()
