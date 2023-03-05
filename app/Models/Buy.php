<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class Buy extends Model
{
    use HasFactory;

    protected $table = 'buy';

    protected $casts = [
        'cancellation' => "boolean",
        'passenger_ids' => 'array'
    ];

    public function Reserve(): BelongsTo
    {
        return $this->belongsTo(Reservation::class);
    }
}
