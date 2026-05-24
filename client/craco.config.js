module.exports = {
  webpack: {
    configure: (webpackConfig) => {
      // Externalize electron and native modules
      webpackConfig.externals = {
        ...webpackConfig.externals,
        electron: "commonjs electron",
        "electron-store": "commonjs electron-store",
      };

      return webpackConfig;
    },
  },
};
