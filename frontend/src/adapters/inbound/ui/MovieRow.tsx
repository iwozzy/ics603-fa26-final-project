import { useState } from 'react';
import { Image, StyleSheet, Text, View } from 'react-native';
import type { MovieSummary } from '../../../domain/timeline';

const months = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

export function MovieRow({ movie }: { movie: MovieSummary }) {
  const [failedUrl, setFailedUrl] = useState<string | null>(null);
  const [year, month] = movie.releaseDate.split('-');
  return <View style={styles.row}>
    <View testID="poster-slot" aria-hidden style={styles.poster}>
      {movie.posterImageUrl && movie.posterImageUrl !== failedUrl &&
        <Image accessible={false} source={{ uri: movie.posterImageUrl }} resizeMode="cover"
          style={StyleSheet.absoluteFill} onError={() => setFailedUrl(movie.posterImageUrl)} />}
    </View>
    <View style={styles.details}>
      <Text accessibilityRole="header" style={styles.title}>{movie.title}</Text>
      <Text style={styles.date}>{months[Number(month) - 1]}, {year}</Text>
      {movie.overview && <Text style={styles.overview}>{movie.overview}</Text>}
    </View>
  </View>;
}

const styles = StyleSheet.create({
  row: { width: '100%', maxWidth: 880, alignSelf: 'center', paddingVertical: 16, paddingHorizontal: 20, flexDirection: 'row', alignItems: 'center', gap: 20 },
  poster: { width: 112, height: 160, flexShrink: 0, overflow: 'hidden', borderRadius: 4, backgroundColor: '#eff0f2' },
  details: { flex: 1, minWidth: 0, gap: 8 },
  title: { fontSize: 23, fontWeight: '600', color: '#22262c' },
  date: { fontSize: 15, color: '#59616b' },
  overview: { fontSize: 16, lineHeight: 23, color: '#343941' },
});
