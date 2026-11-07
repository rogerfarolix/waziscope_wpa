<?php

namespace Tests\Feature;

use Tests\TestCase;

/**
 * Le proxy /download ne doit relayer que les CDN vidéo autorisés (anti-SSRF).
 */
class DownloadProxyTest extends TestCase
{
    public static function forbiddenUrls(): array
    {
        return [
            'localhost'         => ['http://127.0.0.1:8032/health'],
            'ip interne'        => ['http://169.254.169.254/latest/meta-data/'],
            'domaine quelconque'=> ['https://evil.example.com/video.mp4'],
            'suffixe piégé'     => ['https://tiktok.com.evil.com/v.mp4'],
            'préfixe piégé'     => ['https://eviltiktok.com/v.mp4'],
        ];
    }

    #[DataProvider('forbiddenUrls')]
    public function test_rejects_non_whitelisted_hosts(string $url): void
    {
        $this->getJson('/api/v1/download?url=' . urlencode($url))
            ->assertStatus(403)
            ->assertJson(['success' => false]);
    }

    #[DataProvider('forbiddenUrls')]
    public function test_strip_rejects_non_whitelisted_hosts(string $url): void
    {
        $this->getJson('/api/v1/strip?url=' . urlencode($url))->assertStatus(403);
    }

    public function test_requires_valid_url(): void
    {
        $this->getJson('/api/v1/download?url=not-a-url')->assertStatus(422);
    }
}
