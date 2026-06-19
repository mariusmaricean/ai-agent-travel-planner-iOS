import SwiftUI

struct TripCard: View {
    var trip: TripOption
    var isActive: Bool
    var isSaved: Bool
    var onSelect: () -> Void
    var onSave: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .top, spacing: 12) {
                VStack(alignment: .leading, spacing: 4) {
                    Text(trip.name)
                        .font(.headline)
                    Text("\(trip.route) | score \(trip.score)")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    Text(trip.meta)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }

                Spacer()

                Text(dollars(trip.fare))
                    .font(.headline)
                    .foregroundStyle(.white)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 8)
                    .background(TravelPlannerColor.teal, in: RoundedRectangle(cornerRadius: 10, style: .continuous))
            }

            VStack(spacing: 8) {
                ForEach(trip.days) { day in
                    HStack(alignment: .top, spacing: 10) {
                        Text(day.label)
                            .font(.caption.weight(.bold))
                            .foregroundStyle(.white)
                            .frame(width: 34, height: 34)
                            .background(TravelPlannerColor.gold, in: Circle())

                        VStack(alignment: .leading, spacing: 2) {
                            Text(day.title)
                                .font(.subheadline.weight(.semibold))
                            Text(day.detail)
                                .font(.caption)
                                .foregroundStyle(.secondary)
                                .fixedSize(horizontal: false, vertical: true)
                        }

                        Spacer()
                    }
                    .padding(10)
                    .background(TravelPlannerColor.paper, in: RoundedRectangle(cornerRadius: 12, style: .continuous))
                }
            }

            HStack(spacing: 10) {
                Button(action: onSelect) {
                    Label("Select", systemImage: "checkmark.circle")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.bordered)

                Button(action: onSave) {
                    Label(isSaved ? "Saved" : "Save", systemImage: isSaved ? "checkmark" : "tray.and.arrow.down")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .tint(isSaved ? TravelPlannerColor.coral : TravelPlannerColor.teal)
            }
        }
        .padding(14)
        .background(.white, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 16, style: .continuous)
                .stroke(isActive ? TravelPlannerColor.teal.opacity(0.55) : Color.black.opacity(0.06), lineWidth: isActive ? 2 : 1)
        }
    }
}
