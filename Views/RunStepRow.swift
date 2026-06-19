import SwiftUI

struct RunStepRow: View {
    var step: RunStep

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: step.status == .done ? "checkmark" : step.symbol)
                .foregroundStyle(iconColor)
                .frame(width: 36, height: 36)
                .background(iconBackground, in: Circle())

            VStack(alignment: .leading, spacing: 3) {
                Text(step.title)
                    .font(.subheadline.weight(.semibold))
                Text(step.detail)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }

            Spacer()

            Text(step.tag)
                .font(.caption2.weight(.bold))
                .foregroundStyle(.secondary)
                .padding(.horizontal, 8)
                .padding(.vertical, 5)
                .background(TravelPlannerColor.paper, in: Capsule())
        }
        .padding(12)
        .background(.white, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
    }

    private var iconColor: Color {
        switch step.status {
        case .queued: .secondary
        case .active: .white
        case .done: .white
        }
    }

    private var iconBackground: Color {
        switch step.status {
        case .queued: TravelPlannerColor.paper
        case .active: TravelPlannerColor.teal
        case .done: TravelPlannerColor.lime
        }
    }
}
