#pragma once

#include "caffe2/contrib/transform/transform.h"
#include "caffe2/contrib/transform/transforms/single_op_transform.h"
#include "caffe2/core/common.h"
#include "caffe2/proto/caffe2.pb.h"
#include "caffe2/utils/proto_utils.h"

namespace caffe2 {

class ConvToNNPackTransform : public SingleOpTransform {
 protected:
  // Specify what the op needs to be to match the pattern.
  bool MatchOperator(const OperatorDef& op) override {
    return (
        op.type() == "Conv" && op.device_option().device_type() == CPU &&
        op.engine() != "NNPACK");
  }

  // Specify how the operator should be replaced.
  void ReplaceOperator(OperatorDef* op) override {
    op->set_engine("NNPACK");
  }
};

REGISTER_TRANSFORM(ConvToNNPack, ConvToNNPackTransform);

} // namespace caffe2
