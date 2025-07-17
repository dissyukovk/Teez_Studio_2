const webpack = require('webpack');
const path = require('path');

module.exports = function override(config, env) {
  config.resolve.fallback = {
    ...config.resolve.fallback,
    crypto: require.resolve("crypto-browserify"),
    buffer: require.resolve("buffer/"),
    stream: require.resolve("stream-browserify"),
    vm: require.resolve("vm-browserify"),
    // не добавляем fallback для process
  };

  config.resolve.alias = {
    ...config.resolve.alias,
    process: require.resolve("process"),
    "process/browser": require.resolve("process"),
  };

  config.plugins = [
    ...(config.plugins || []),
    new webpack.ProvidePlugin({
      Buffer: ["buffer", "Buffer"],
      process: "process",
    }),
  ];

  return config;
};
