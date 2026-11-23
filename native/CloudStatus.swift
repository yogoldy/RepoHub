import Foundation

final class ProgressStore: @unchecked Sendable {
    private let lock = NSLock()
    private var items: [String: Progress] = [:]
    func set(_ id: String, _ progress: Progress) { lock.lock(); defer { lock.unlock() }; items[id] = progress }
    func get(_ id: String) -> Progress? { lock.lock(); defer { lock.unlock() }; return items[id] }
    func remove(_ id: String) { lock.lock(); defer { lock.unlock() }; items.removeValue(forKey: id) }
}

// Read-only adapter for documented Foundation iCloud upload attributes.
let input = FileHandle.standardInput.readDataToEndOfFile()
var output: [String: [String: Any]] = [:]
if let requests = try? JSONSerialization.jsonObject(with: input) as? [[String: String]] {
    // Published progress is separate from upload acknowledgement. Never infer
    // completion from a fraction, including 100%, and never invent missing data.
    let progressByID = ProgressStore()
    let subscribers = requests.compactMap { request -> Any? in
        guard let id = request["id"], let path = request["path"] else { return nil }
        return Progress.addSubscriber(forFileURL: URL(fileURLWithPath: path)) { progress in
            progressByID.set(id, progress)
            return { progressByID.remove(id) }
        }
    }
    let deadline = Date(timeIntervalSinceNow: 0.8)
    while Date() < deadline { RunLoop.current.run(until: Date(timeIntervalSinceNow: 0.05)) }
    for request in requests {
        guard let id = request["id"], let path = request["path"] else { continue }
        var url = URL(fileURLWithPath: path)
        url.removeAllCachedResourceValues()
        var item: [String: Any] = [:]
        if let progress = progressByID.get(id), !progress.isIndeterminate,
           progress.totalUnitCount > 0, progress.fractionCompleted.isFinite,
           (0...1).contains(progress.fractionCompleted) {
            item["percent"] = progress.fractionCompleted * 100
            item["progress_source"] = "macOS published progress"
        }
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
    subscribers.forEach { Progress.removeSubscriber($0) }
}
let data = try JSONSerialization.data(withJSONObject: output, options: [.sortedKeys])
FileHandle.standardOutput.write(data)
