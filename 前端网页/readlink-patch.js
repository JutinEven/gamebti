/**
 * ============================================
 * Node.js v24 Windows readlink EISDIR 补丁
 * ============================================
 *
 * Node 24 (v24.16.0) 在 Windows 上对普通文件调用
 * fs.readlinkSync / fs.readlink 会抛出 EISDIR 错误，
 * 而不是预期的 EINVAL。
 *
 * 此补丁拦截 EISDIR 错误并转为 EINVAL，使 webpack 的
 * enhanced-resolve 库能正常降级处理路径解析。
 *
 * 用法：node --require ./readlink-patch.js ...
 * ============================================
 */

const fs = require("fs");

const originalReadlinkSync = fs.readlinkSync;
const originalReadlink = fs.readlink;

/**
 * 补丁版 readlinkSync
 * 当遇到 EISDIR 错误时，将错误码改为 EINVAL
 * 让调用者知道这不是一个有效的 symlink
 */
fs.readlinkSync = function patchedReadlinkSync(path, options) {
  try {
    return originalReadlinkSync.call(fs, path, options);
  } catch (err) {
    if (err && err.code === "EISDIR") {
      const newErr = new Error(
        `EINVAL: invalid argument, readlink '${path}'`
      );
      newErr.code = "EINVAL";
      newErr.errno = -4071;
      newErr.syscall = "readlink";
      newErr.path = path;
      throw newErr;
    }
    throw err;
  }
};

/**
 * 补丁版 readlink (异步)
 */
fs.readlink = function patchedReadlink(path, options, callback) {
  // 兼容两种调用方式: readlink(path, callback) 和 readlink(path, options, callback)
  if (typeof options === "function") {
    callback = options;
    options = undefined;
  }

  if (typeof callback === "function") {
    originalReadlink.call(fs, path, options, (err, result) => {
      if (err && err.code === "EISDIR") {
        const newErr = new Error(
          `EINVAL: invalid argument, readlink '${path}'`
        );
        newErr.code = "EINVAL";
        newErr.errno = -4071;
        newErr.syscall = "readlink";
        newErr.path = path;
        callback(newErr);
      } else {
        callback(err, result);
      }
    });
  } else {
    return originalReadlink.call(fs, path, options).catch((err) => {
      if (err && err.code === "EISDIR") {
        const newErr = new Error(
          `EINVAL: invalid argument, readlink '${path}'`
        );
        newErr.code = "EINVAL";
        newErr.errno = -4071;
        newErr.syscall = "readlink";
        newErr.path = path;
        throw newErr;
      }
      throw err;
    });
  }
};

// Patch applied silently
