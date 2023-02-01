import numpy as np
import torch
from torch import nn
import torch.nn.functional as F
from beartype import beartype
from beartype.typing import List, Optional, Union, Dict
from clap import CLAP
from vector_quantize_pytorch import ResidualVQ
from einops import rearrange

from utils import exists


@beartype
class ClapQuantized(nn.Module):
    def __init__(self,
                 *,
                 clap: CLAP,
                 clap_cfg: Dict[str, any],
                 codebook_size: int = 1024,
                 rq_num_quantizers: int = 12,
                 rq_ema_decay: float = 0.95,
                 ):
        super().__init__()

        self.clap = clap
        self.clap_cfg = clap_cfg

        for param in self.clap.parameters():
            param.requires_grad = False

        self.rq = ResidualVQ(
            dim=clap.joint_embed_shape,
            num_quantizers=rq_num_quantizers,  # specify number of quantizers
            codebook_size=codebook_size,  # codebook size
            commitment_weight=0,  # embeddings are frozen so no need for commitment loss
            decay=rq_ema_decay,
            kmeans_init=True,
            threshold_ema_dead_code=2,
        )

    def forward(self,
                *,
                audio_input: Optional[List[Dict]] = None,
                text_embed: Optional[Dict] = None,
                ):
        """
        Wrapper for clap module that takes in audio or text and returns the quantized embedding from the respective tower
        :param audio_input: list of audio features generated by get_audio_features
        :param text_embed: text embeddings from tokenizer
        """

        assert exists(audio_input) ^ exists(
            text_embed), "either audio or text must be provided, but not both"

        with torch.no_grad():
            self.clap.eval()
            if exists(audio_input):
                embedding = self.clap.get_audio_embedding(audio_input)
            else:
                embedding = self.clap.get_text_embedding(text_embed)

        print(embedding.shape)

        _, indices, _ = self.rq(rearrange(embedding, 'n c -> 1 n c'))

        return indices