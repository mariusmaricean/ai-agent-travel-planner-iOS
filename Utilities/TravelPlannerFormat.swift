import Foundation

enum TravelPlannerFormat {
    static let currency: NumberFormatter = {
        let formatter = NumberFormatter()
        formatter.numberStyle = .currency
        formatter.currencyCode = "EUR"
        formatter.maximumFractionDigits = 0
        return formatter
    }()
}

func dollars(_ value: Double) -> String {
    TravelPlannerFormat.currency.string(from: NSNumber(value: value)) ?? "$\(Int(value))"
}
