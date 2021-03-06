from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from caffe2.python import schema
from caffe2.python.layers.arc_cosine_feature_map import ArcCosineFeatureMap
import numpy as np


class SemiRandomFeatures(ArcCosineFeatureMap):
    """
    Implementation of the semi-random kernel feature map.

    Applies H(x_rand) * x_rand^s * x_learned, where
        H is the Heaviside step function,
        x_rand is the input after applying FC with randomized parameters,
        and x_learned is the input after applying FC with learnable parameters.

    If using multilayer model with semi-random layers, then input and output records
    should have a 'full' and 'random' Scalar. The random Scalar will be passed as
    input to process the random features.

    For more information, see the original paper:
        https://arxiv.org/pdf/1702.08882.pdf

    Inputs :
        output_dims -- dimensions of the output vector
        s -- if s == 0, will obtain linear semi-random features;
             else if s == 1, will obtain squared semi-random features;
             else s >= 2, will obtain higher order semi-random features
        scale -- amount to scale the standard deviation
        weight_init -- initialization distribution for weight parameter
        bias_init -- initialization distribution for bias pararmeter
        weight_optim -- optimizer for weight params for learned features
        bias_optim -- optimizer for bias param for learned features
        set_weight_as_global_constant -- if True, initialized random parameters
                                         will be constant across all distributed
                                         instances of the layer
    """
    def __init__(
            self,
            model,
            input_record,
            output_dims,
            s=0,
            scale=None,
            weight_init=None,
            bias_init=None,
            weight_optim=None,
            bias_optim=None,
            set_weight_as_global_constant=False,
            name='semi_random_features',
            **kwargs):

        if isinstance(input_record, schema.Struct):
            schema.is_schema_subset(
                schema.Struct(
                    ('full', schema.Scalar()),
                    ('random', schema.Scalar()),
                ),
                input_record
            )
            self.input_record_full = input_record.full
            self.input_record_random = input_record.random

        elif isinstance(input_record, schema.Scalar):
            self.input_record_full = input_record
            self.input_record_random = input_record

        super(SemiRandomFeatures, self).__init__(
            model,
            self.input_record_full,
            output_dims,
            s=s,
            scale=scale,
            weight_init=weight_init,
            bias_init=bias_init,
            weight_optim=None,
            bias_optim=None,
            set_weight_as_global_constant=set_weight_as_global_constant,
            initialize_output_schema=False,
            name=name,
            **kwargs)

        self.output_schema = schema.Struct(
            ('full', schema.Scalar(
                (np.float32, output_dims),
                model.net.NextScopedBlob(name + '_full_output')
            ),),
            ('random', schema.Scalar(
                (np.float32, output_dims),
                model.net.NextScopedBlob(name + '_random_output')
            ),),
        )

        # Learned Parameters
        self.learned_w = self.model.net.NextScopedBlob(self.name + "_learned_w")
        self.learned_b = self.model.net.NextScopedBlob(self.name + "_learned_b")
        self.params += self._initialize_params(self.learned_w,
                                               self.learned_b,
                                               w_init=weight_init,
                                               b_init=bias_init,
                                               w_optim=weight_optim,
                                               b_optim=bias_optim)

    def add_ops(self, net):
        # Learned features: wx + b
        learned_features = net.FC(self.input_record_full.field_blobs() +
                                  [self.learned_w, self.learned_b],
                                  net.NextScopedBlob('learned_features'))
        # Random features: wx + b
        random_features = net.FC(self.input_record_random.field_blobs() +
                                 [self.random_w, self.random_b],
                                 net.NextScopedBlob('random_features'))
        processed_random_features = self._heaviside_with_power(
            net,
            random_features,
            self.output_schema.random.field_blobs(),
            self.s
        )
        net.Mul([processed_random_features, learned_features],
                self.output_schema.full.field_blobs())
