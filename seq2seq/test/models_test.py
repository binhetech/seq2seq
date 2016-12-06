"""
Tests for Models
"""

import seq2seq
from collections import namedtuple
from seq2seq.models import BasicSeq2Seq, AttentionSeq2Seq
from seq2seq.decoders import FixedDecoderInputs, DynamicDecoderInputs

import tensorflow as tf
import numpy as np

class EncoderDecoderTests(object):
  def __init__(self):
    self.batch_size = 4
    self.vocab_size = 100
    self.input_depth = 32
    self.max_decode_length = 40

  def create_model(self):
    raise NotImplementedError

  def _create_example(self):
    source = np.random.randn(self.batch_size, self.max_decode_length, self.input_depth)
    source_len = np.random.randint(0, self.max_decode_length, [self.batch_size])
    target_len = np.random.randint(0, self.max_decode_length, [self.batch_size])
    target = np.random.randn(self.batch_size, np.max(target_len), self.input_depth)
    labels = np.random.randint(0, self.vocab_size, [self.batch_size, np.max(target_len) - 1])

    example_ = namedtuple("Example", ["source", "source_len", "target", "target_len", "labels"])
    return example_(source, source_len, target, target_len, labels)

  def test_forward_pass(self):
    ex = self._create_example()
    decoder_input_fn = FixedDecoderInputs(
      inputs=tf.convert_to_tensor(ex.target, dtype=tf.float32),
      sequence_length=tf.convert_to_tensor(ex.target_len, dtype=tf.int32))

    model = self.create_model()
    decoder_output, log_perplexities = model._encode_decode(
      source=tf.convert_to_tensor(ex.source, dtype=tf.float32),
      source_len=tf.convert_to_tensor(ex.source_len, dtype=tf.int32),
      decoder_input_fn=decoder_input_fn,
      target_len=tf.convert_to_tensor(ex.target_len, dtype=tf.int32),
      labels=tf.convert_to_tensor(ex.labels, dtype=tf.int32))

    with self.test_session() as sess:
      sess.run(tf.global_variables_initializer())
      decoder_output_, log_perplexities_ = sess.run([decoder_output, log_perplexities])

    # Assert shapes are correct
    np.testing.assert_array_equal(log_perplexities_.shape, [self.batch_size])
    np.testing.assert_array_equal(
      decoder_output_.logits.shape,
      [self.batch_size, np.max(ex.target_len), model.target_vocab_info.total_size])
    np.testing.assert_array_equal(
      decoder_output_.predictions.shape,
      [self.batch_size, np.max(ex.target_len)])


  def test_inference(self):
    model = self.create_model()
    ex = self._create_example()

    embeddings = tf.get_variable("W_embed", [model.target_vocab_info.total_size, self.input_depth])
    def make_input_fn(step_output):
      """Looks up the predictions in the embeddings.
      """
      return tf.nn.embedding_lookup(embeddings, step_output.predictions)

    decoder_input_fn = DynamicDecoderInputs(
      initial_inputs=tf.zeros([self.batch_size, self.input_depth], dtype=tf.float32),
      make_input_fn=make_input_fn)

    decoder_output, log_perplexities = model._encode_decode(
      source=tf.convert_to_tensor(ex.source, dtype=tf.float32),
      source_len=tf.convert_to_tensor(ex.source_len, dtype=tf.int32),
      decoder_input_fn=decoder_input_fn,
      target_len=self.max_decode_length)

    with self.test_session() as sess:
      sess.run(tf.global_variables_initializer())
      decoder_output_ = sess.run(decoder_output)

    # Assert shapes are correct
    self.assertIsNone(log_perplexities)
    np.testing.assert_array_equal(
      decoder_output_.logits.shape,
      [self.batch_size, self.max_decode_length, model.target_vocab_info.total_size])
    np.testing.assert_array_equal(
      decoder_output_.predictions.shape,
      [self.batch_size, self.max_decode_length])

  def test_gradients(self):
    ex = self._create_example()
    decoder_input_fn = FixedDecoderInputs(
      inputs=tf.convert_to_tensor(ex.target, dtype=tf.float32),
      sequence_length=tf.convert_to_tensor(ex.target_len, dtype=tf.int32))

    model = self.create_model()
    decoder_output, log_perplexities = model._encode_decode(
      source=tf.convert_to_tensor(ex.source, dtype=tf.float32),
      source_len=tf.convert_to_tensor(ex.source_len, dtype=tf.int32),
      decoder_input_fn=decoder_input_fn,
      target_len=tf.convert_to_tensor(ex.target_len, dtype=tf.int32),
      labels=tf.convert_to_tensor(ex.labels, dtype=tf.int32))

    mean_loss = tf.reduce_mean(log_perplexities)
    optimizer = tf.train.AdamOptimizer()
    grads_and_vars = optimizer.compute_gradients(mean_loss)
    train_op = optimizer.apply_gradients(grads_and_vars)

    with self.test_session() as sess:
      sess.run(tf.global_variables_initializer())
      _, grads_and_vars_ = sess.run([train_op, grads_and_vars])

    for grad, var in grads_and_vars_:
      self.assertFalse(np.isnan(grad).any())


class TestBasicSeq2Seq(tf.test.TestCase, EncoderDecoderTests):
  def setUp(self):
    tf.test.TestCase.setUp(self)
    EncoderDecoderTests.__init__(self)

  def create_model(self):
    vocab_info = seq2seq.inputs.VocabInfo(
      "", self.vocab_size, seq2seq.inputs.get_special_vocab(self.vocab_size))
    return BasicSeq2Seq(
      source_vocab_info=vocab_info,
      target_vocab_info=vocab_info,
      params=BasicSeq2Seq.default_params())

class TestAttentionSeq2Seq(tf.test.TestCase, EncoderDecoderTests):
  def setUp(self):
    tf.test.TestCase.setUp(self)
    EncoderDecoderTests.__init__(self)
    self.encoder_rnn_cell = tf.nn.rnn_cell.LSTMCell(32)
    self.decoder_rnn_cell = tf.nn.rnn_cell.LSTMCell(32)
    self.attention_dim = 128

  def create_model(self):
    vocab_info = seq2seq.inputs.VocabInfo(
      "", self.vocab_size, seq2seq.inputs.get_special_vocab(self.vocab_size))
    return AttentionSeq2Seq(
      source_vocab_info=vocab_info,
      target_vocab_info=vocab_info,
      params=AttentionSeq2Seq.default_params())

if __name__ == "__main__":
  tf.test.main()
