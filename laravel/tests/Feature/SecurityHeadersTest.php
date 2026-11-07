<?php

namespace Tests\Feature;

use Illuminate\Support\Facades\Http;
use Tests\TestCase;

class SecurityHeadersTest extends TestCase
{
    public function test_csp_forbids_inline_and_eval_scripts(): void
    {
        $csp = $this->get('/')->headers->get('Content-Security-Policy');
        $this->assertNotNull($csp);
        $this->assertStringContainsString("script-src 'self'", $csp);
        $this->assertStringNotContainsString('unsafe-eval', $csp);
        $this->assertStringContainsString("frame-ancestors 'none'", $csp);
    }

    public function test_status_endpoint_proxies_extractor(): void
    {
        Http::fake(['*/status' => Http::response(['platforms' => ['tiktok' => true, 'facebook' => false], 'checked_at' => 1])]);
        $this->getJson('/api/v1/status')
            ->assertOk()
            ->assertJsonPath('platforms.facebook', false);
    }
}
