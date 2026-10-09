import Foundation

// Read-only adapter for documented Foundation iCloud upload attributes.
let input = FileHandle.standardInput.readDataToEndOfFile()
var output: [String: [String: Any]] = [:]
if let requests = try? JSONSerialization.jsonObject(with: input) as? [[String: String]] {
    for request in requests {
        guard let id = request["id"], let path = request["path"] else { continue }
        var url = URL(fileURLWithPath: path)
        url.removeAllCachedResourceValues()
        var item: [String: Any] = [:]
        do {
            let values = try url.resourceValues(forKeys: [.isUbiquitousItemKey, .ubiquitousItemIsUploadedKey,
                .ubiquitousItemIsUploadingKey, .ubiquitousItemUploadingErrorKey, .ubiquitousItemHasUnresolvedConflictsKey])
            item["ubiquitous"] = values.isUbiquitousItem
            item["uploaded"] = values.ubiquitousItemIsUploaded
            item["uploading"] = values.ubiquitousItemIsUploading
            item["error"] = values.ubiquitousItemUploadingError?.localizedDescription
            if let error = values.ubiquitousItemUploadingError {
                item["error_domain"] = error.domain
                item["error_code"] = error.code
                if let underlying = error.userInfo[NSUnderlyingErrorKey] as? NSError {
                    item["underlying_domain"] = underlying.domain
                    item["underlying_code"] = underlying.code
                }
            }
            item["conflicts"] = values.ubiquitousItemHasUnresolvedConflicts
        } catch { item["probe_error"] = error.localizedDescription }
        output[id] = item
    }
}
let data = try JSONSerialization.data(withJSONObject: output, options: [.sortedKeys])
FileHandle.standardOutput.write(data)
