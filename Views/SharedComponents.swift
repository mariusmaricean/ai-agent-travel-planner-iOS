import SwiftUI

struct FieldCard<Content: View>: View {
    var title: String
    @ViewBuilder var content: Content

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title.uppercased())
                .font(.caption2.weight(.bold))
                .foregroundStyle(.secondary)
            content
                .font(.body.weight(.semibold))
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(.white, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
    }
}

struct SectionHeader: View {
    var title: String
    var subtitle: String

    var body: some View {
        VStack(alignment: .leading, spacing: 3) {
            Text(title)
                .font(.headline)
            Text(subtitle)
                .font(.caption)
                .foregroundStyle(.secondary)
        }
    }
}

struct MetricCard: View {
    var value: String
    var label: String
    var color: Color

    var body: some View {
        VStack(spacing: 4) {
            Text(value)
                .font(.title3.weight(.black))
            Text(label.uppercased())
                .font(.caption2.weight(.bold))
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity)
        .frame(height: 74)
        .background(color, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
    }
}

struct StatusChip: View {
    var text: String

    var body: some View {
        VStack(spacing: 3) {
            Text(text)
                .font(.headline.weight(.black))
            Text("Agent")
                .font(.caption2.weight(.bold))
                .textCase(.uppercase)
        }
        .foregroundStyle(.white)
        .padding(.horizontal, 12)
        .padding(.vertical, 9)
        .background(TravelPlannerColor.teal.opacity(0.95), in: RoundedRectangle(cornerRadius: 12, style: .continuous))
    }
}

struct EmptyStateView: View {
    var text: String

    var body: some View {
        Text(text)
            .font(.subheadline)
            .foregroundStyle(.secondary)
            .frame(maxWidth: .infinity)
            .padding(18)
            .background(.white, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
    }
}
