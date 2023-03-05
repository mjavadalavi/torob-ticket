<?php

namespace App\Http\Controllers\API;

use App\Classes\ProjectResource;
use App\Http\Controllers\Controller;
use App\Http\Requests\ListWeeklyScheduleRequest;
use App\Http\Requests\StoreWeeklyScheduleRequest;
use App\Models\WeeklySchedule;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\Response;

class WeeklyScheduleController extends Controller
{
    /**
     * @OA\Get(
     *      path="/index",
     *      operationId="Lists",
     *      tags={"source", "destination", "terminals"},
     *      summary="Get list of source, destination or terminals ",
     *      description="Returns list of source, destination or terminals",
     *      @OA\Response(
     *          response=200,
     *          description="Successful operation",
     *          @OA\JsonResponse(ref="#/components/schemas/ProjectResource")
     *       ),
     *      @OA\Response(
     *          response=404,
     *          description="Not Found"
     *      )
     *     )
     */
    public function index(ListWeeklyScheduleRequest $request)
    {
        $validate = $request->validated();
        $data = null;
        if($validate){
            switch ($request->input("actions")){
                case "terminals":
                    $data = WeeklySchedule::groupBy("source_city_id")->get();
                    break;
                case "destination":
                    $data = WeeklySchedule::groupBy("destination_city_id")->get();
                    break;
                case "source":
                    $data = WeeklySchedule::groupBy("source_terminal_id")->get();
                    break;
            }
            if ($data == null)
                return response("null", 404)->header('Content-Type', 'application/json');
            else
                return response()->json($data)->header('Content-Type', 'application/json');
        }
    }

    /**
     * @OA\Post(
     *      path="/projects",
     *      operationId="storeweeklyschedule",
     *      tags={"WeeklySchedule"},
     *      summary="Store new WeeklySchedule",
     *      description="Returns json of result storing data",
     *      @OA\RequestBody(
     *          required=true,
     *          @OA\JsonContent(ref="#/components/schemas/StoreWeeklyScheduleRequest")
     *      ),
     *      @OA\Response(
     *          response=201,
     *          description="Successful operation",
     *          @OA\JsonContent(ref="#/components/schemas/WeeklySchedule")
     *       ),
     *      @OA\Response(
     *          response=400,
     *          description="Bad Request"
     *      )
     * )
     */
    public function store(StoreWeeklyScheduleRequest $request)
    {
        $project = WeeklySchedule::create($request->all());

        return (new ProjectResource($project))
            ->response()
            ->setStatusCode(Response::HTTP_CREATED);
    }

    /**
     * Display the specified resource.
     */
    public function show(string $id)
    {
        //
    }

    /**
     * Update the specified resource in storage.
     */
    public function update(Request $request, string $id)
    {
        //
    }

    /**
     * Remove the specified resource from storage.
     */
    public function destroy(string $id)
    {
        //
    }
}
